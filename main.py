from fastapi import FastAPI, UploadFile, Form, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import (
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, Response
from fastapi.exceptions import HTTPException
from pydantic import BaseModel
import uvicorn
import functools
import sqlalchemy
import os
import hashlib
from sqlalchemy import create_engine, func, desc
from sqlalchemy.dialects.mysql import Insert as insert
from sqlalchemy.orm import Session
from ucloud.core import exc
from ucloud.client import Client

from sql_tables import *
from config import MysqlConfig, WebConfig, CDNConfig


CDN_URL = "https://cdn.leavesmc.z0z0r4.top"
SECRET = open("config/secret", "r").read()


def sql_replace(sess: Session, table, **kwargs):
    insert_stmt = insert(table).values(kwargs)
    on_duplicate_key_stmt = insert_stmt.on_duplicate_key_update(**kwargs)
    sess.execute(on_duplicate_key_stmt)


app = FastAPI(description="LeavesMC website API", version="0.1.0", title="LeavesMC")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex="https://.*\.leavesmc\.(top|org)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# docs
app.mount("/static", StaticFiles(directory="static"), name="static")

# cdn_download_file
os.makedirs("cache", exist_ok=True)
app.mount("/cache", StaticFiles(directory="cache"), name="cache")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return RedirectResponse("https://docs.leavesmc.top/img/logo.svg")


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="/static/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui.css",
    )


@app.get(app.swagger_ui_oauth2_redirect_url, include_in_schema=False)
async def swagger_ui_redirect():
    return get_swagger_ui_oauth2_redirect_html()


def api_json_middleware(callback):
    @functools.wraps(callback)
    async def w(*args, **kwargs):
        try:
            res = await callback(*args, **kwargs)
            return res
        except sqlalchemy.exc.OperationalError:
            await _startup()
            res = await callback(*args, **kwargs)
            return res

    return w


@app.on_event("startup")
async def _startup():
    MysqlConfig.load()
    app.state.sql_engine = create_engine(
        f"mysql+pymysql://{MysqlConfig.user}:{MysqlConfig.password}@{MysqlConfig.host}:{MysqlConfig.port}/{MysqlConfig.database}?autocommit=1",
        pool_size=128,
        max_overflow=32,
        pool_pre_ping=True,
        pool_recycle=3600,
    )


@app.get("/", description="Root")
@api_json_middleware
async def root():
    return "LeavesMC API"


@app.get(
    "/projects",
    description="projects list",
    responses={
        200: {
            "content": {"application/json": {"example": {"projects": ["leaves"]}}},
        }
    },
)
@api_json_middleware
async def projects():
    with Session(bind=app.state.sql_engine) as sess:
        project_id_list = sess.query(Project.project_id).distinct().all()
    return {"projects": [project for project in project_id_list[0]]}


@app.get(
    "/projects/{project}",
    description="project info",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "project_id": "leaves",
                        "project_name": "Leaves",
                        "version_groups": ["1.19", "1.20"],
                        "versions": [
                            "1.19",
                            "1.19.1",
                            "1.19.2",
                            "1.19.3",
                            "1.19.4",
                            "1.20",
                            "1.20.1",
                        ],
                    }
                }
            },
        }
    },
)
@api_json_middleware
async def project_info(project: str = "leaves"):
    with Session(bind=app.state.sql_engine) as sess:
        result = (
            sess.query(Project.project_name, Project.version, Project.version_group)
            .where(Project.project_id == project)
            .distinct()
            .all()
        )
        if result == ():
            raise HTTPException(status_code=404, detail=f"{project} not found")

        project_info = {
            "project_id": project,
            "project_name": result[0]["project_name"],
            "version_groups": [],
            "versions": [],
        }
        for res in result:
            if res[1] not in project_info["versions"]:
                project_info["versions"].append(res[1])
            if res[2] not in project_info["version_groups"]:
                project_info["version_groups"].append(res[2])

        return project_info


@app.get(
    "/projects/{project}/versions/{version}",
    description="project version info",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "project_id": "leaves",
                        "project_name": "leaves",
                        "version": "1.20.1",
                        "builds": [4, 5],
                    }
                }
            },
        }
    },
)
@api_json_middleware
async def project_version_info(project: str = "leaves", version: str = "1.20.1"):
    with Session(bind=app.state.sql_engine) as sess:
        result = (
            sess.query(Project.build)
            .filter(Project.project_id == project, Project.version == version)
            .all()
        )
    if len(result) == 0:
        raise HTTPException(status_code=404, detail=f"{project} or {version} not found")
    return {
        "project_id": project,
        "project_name": project,
        "version": version,
        "builds": [build[0] for build in result if result != ()],
    }


@app.get(
    "/projects/{project}/versions/{version}/builds",
    description="project version builds info",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "project_id": "leaves",
                        "project_name": "leaves",
                        "version": "1.20.1",
                        "builds": [
                            {
                                "build": 4,
                                "time": "2023-06-14T03:10:50.000Z",
                                "channel": "experimental",
                                "promoted": False,
                                "changes": [
                                    {
                                        "commit": "494cb91a51fa591a3152841c9277ecd7dd6bbdd6",
                                        "summary": "Update 1.20.1",
                                        "message": "Update 1.20.1\n",
                                    }
                                ],
                                "downloads": {
                                    "application": {
                                        "name": "leaves-1.20.1.jar",
                                        "sha256": "3bc74a7d33063921ea22424ae9246c026009bfc98f33ee374d38b3dd89d63636",
                                        "url": "https://github.com/LeavesMC/Leaves/releases/download/1.20.1-494cb91/leaves-1.20.1.jar",
                                    }
                                },
                            }
                        ],
                    }
                }
            },
        }
    },
)
@api_json_middleware
async def project_version_builds_info(project: str = "leaves", version: str = "1.20.1"):
    with Session(bind=app.state.sql_engine) as sess:
        build_result = (
            sess.query(Project)
            .filter(Project.project_id == project, Project.version == version)
            .all()
        )
        if len(build_result) == 0:
            raise HTTPException(
                status_code=404, detail=f"{project} or {version} not found"
            )
        download_result = (
            sess.query(File)
            .filter(File.project_id == project, File.version == version)
            .all()
        )
        download_info_by_build = {}
        for download_info in download_result:
            if download_info_by_build.get(download_info.build) is None:  # 3 is build
                download_info_by_build[download_info.build] = {}
            download_info_by_build[download_info.build][download_info.type] = {
                "name": download_info.name,
                "sha256": download_info.sha256,
                "url": download_info.url,
            }

        change_result = (
            sess.query(Commit)
            .filter(Commit.project_id == project, Commit.version == version)
            .all()
        )
        commit_info_by_build = {}
        for commit_info in change_result:
            if commit_info_by_build.get(commit_info.build) is None:  # 3 is build
                commit_info_by_build[commit_info.build] = []
            commit_info_by_build[commit_info.build].append(
                {
                    "commit": commit_info.hash,
                    "summary": commit_info.summary,
                    "message": commit_info.message,
                }
            )

        builds = []
        for build in build_result:
            builds.append(
                {
                    "build": build.build,
                    "time": build.time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                    "channel": build.channel,
                    "promoted": build.promoted,
                    "changes": commit_info_by_build[build.build]
                    if build.build in commit_info_by_build
                    else [],
                    "downloads": download_info_by_build[build.build]
                    if build.build in download_info_by_build
                    else [],
                }
            )

        return {
            "project_id": project,
            "project_name": project,
            "version": version,
            "builds": builds,
        }


@app.get(
    "/projects/{project}/versions/{version}/builds/latest",
    description="get latest build info",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "project_id": "leaves",
                        "project_name": "leaves",
                        "version": "1.20.1",
                        "build": 42,
                        "time": "2023-07-24T08:08:42.000Z",
                        "channel": "default",
                        "promoted": False,
                        "changes": [
                            {
                                "commit": "413f258fb864102e41379fb8fe99d214af4c5bc9",
                                "summary": "Update Paper",
                                "message": "Update Paper\n",
                            },
                            {
                                "commit": "c4aa610b597158d286356827cfa49fcb465f8fb7",
                                "summary": "Fix fakeplayer command and remove",
                                "message": "Fix fakeplayer command and remove\n",
                            },
                            {
                                "commit": "feb7fb43fcee22ca51ca925bba39b4965835aa60",
                                "summary": "Bow infinity fix",
                                "message": "Bow infinity fix\n",
                            },
                        ],
                        "downloads": {
                            "application": {
                                "name": "leaves-1.20.1.jar",
                                "sha256": "c8472025c5cd4cd916af071714b69f0478642b9c829f9d877b607bd3b7c5d5b5",
                                "url": "https://github.com/LeavesMC/Leaves/releases/download/1.20.1-feb7fb4/leaves-1.20.1.jar",
                                "cdn_url": "https://cdn.leavesmc.z0z0r4.top/cache/leaves-1.20.1.jar",
                            }
                        },
                    }
                }
            },
        }
    },
)
async def latest_build_info(project: str = "leaves", version: str = "1.20.1"):
    with Session(bind=app.state.sql_engine) as sess:
        build_result = (
            sess.query(Project)
            .filter(
                Project.project_id == project,
                Project.version == version,
            )
            .order_by(desc(Project.build))
            .limit(1)
            .one_or_none()
        )
        if build_result == None:
            raise HTTPException(
                status_code=404, detail=f"{project} or {version} not found"
            )
        build = build_result.build
        download_result = (
            sess.query(File)
            .filter(
                File.project_id == project,
                File.version == version,
                File.build == build,
            )
            .all()
        )
        downloads_info = {}
        for download_info in download_result:
            downloads_info[download_info.type] = {
                "name": download_info.name,
                "sha256": download_info.sha256,
                "url": download_info.url,
                "cdn_url": CDN_URL + "/cache/" + download_info.name,
            }

        change_result = (
            sess.query(Commit)
            .filter(
                Commit.project_id == project,
                Commit.version == version,
                Commit.build == build,
            )
            .all()
        )
        changes_info = [
            {
                "commit": commit_info.hash,
                "summary": commit_info.summary,
                "message": commit_info.message,
            }
            for commit_info in change_result
        ]

        return {
            "project_id": project,
            "project_name": project,
            "version": version,
            "build": build_result.build,
            "time": build_result.time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "channel": build_result.channel,
            "promoted": build_result.promoted,
            "changes": changes_info,
            "downloads": downloads_info,
        }


@app.get(
    "/projects/{project}/versions/{version}/builds/{build}",
    description="project version build info",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "project_id": "leaves",
                        "project_name": "leaves",
                        "version": "1.20.1",
                        "build": 42,
                        "time": "2023-07-24T08:08:42.000Z",
                        "channel": "default",
                        "promoted": False,
                        "changes": [
                            {
                                "commit": "413f258fb864102e41379fb8fe99d214af4c5bc9",
                                "summary": "Update Paper",
                                "message": "Update Paper\n",
                            },
                            {
                                "commit": "c4aa610b597158d286356827cfa49fcb465f8fb7",
                                "summary": "Fix fakeplayer command and remove",
                                "message": "Fix fakeplayer command and remove\n",
                            },
                            {
                                "commit": "feb7fb43fcee22ca51ca925bba39b4965835aa60",
                                "summary": "Bow infinity fix",
                                "message": "Bow infinity fix\n",
                            },
                        ],
                        "downloads": {
                            "application": {
                                "name": "leaves-1.20.1.jar",
                                "sha256": "c8472025c5cd4cd916af071714b69f0478642b9c829f9d877b607bd3b7c5d5b5",
                                "url": "https://github.com/LeavesMC/Leaves/releases/download/1.20.1-feb7fb4/leaves-1.20.1.jar",
                                "cdn_url": "https://cdn.leavesmc.z0z0r4.top/cache/leaves-1.20.1.jar",
                            }
                        },
                    }
                }
            },
        }
    },
)
@api_json_middleware
async def project_version_build_info(
    build: int, project: str = "leaves", version: str = "1.20.1"
):
    with Session(bind=app.state.sql_engine) as sess:
        build_result = (
            sess.query(Project)
            .filter(
                Project.project_id == project,
                Project.version == version,
                Project.build == build,
            )
            .one_or_none()
        )
        if build_result == None:
            raise HTTPException(
                status_code=404, detail=f"{project} or {version} not found"
            )
        download_result = (
            sess.query(File)
            .filter(
                File.project_id == project,
                File.version == version,
                File.build == build,
            )
            .all()
        )
        downloads_info = {}
        for download_info in download_result:
            downloads_info[download_info.type] = {
                "name": download_info.name,
                "sha256": download_info.sha256,
                "url": download_info.url,
            }

        change_result = (
            sess.query(Commit)
            .filter(
                Commit.project_id == project,
                Commit.version == version,
                Commit.build == build,
            )
            .all()
        )
        changes_info = [
            {
                "commit": commit_info.hash,
                "summary": commit_info.summary,
                "message": commit_info.message,
            }
            for commit_info in change_result
        ]

        return {
            "project_id": project,
            "project_name": project,
            "version": version,
            "build": build_result.build,
            "time": build_result.time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "channel": build_result.channel,
            "promoted": build_result.promoted,
            "changes": changes_info,
            "downloads": downloads_info,
        }


@app.get(
    "/projects/{project}/version_group/{version_group}",
    description="get versions by version_group",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "project_id": "leaves",
                        "project_name": "Leaves",
                        "version_group": "1.20",
                        "versions": ["1.20", "1.20.1"],
                    }
                }
            },
        }
    },
)
@api_json_middleware
async def version_group_info(project: str = "leaves", version_group: str = "1.20"):
    with Session(bind=app.state.sql_engine) as sess:
        result = (
            sess.query(Project.version, Project.project_name)
            .where(Project.version_group == version_group)
            .distinct()
            .all()
        )
        if len(result) == 0:
            raise HTTPException(
                status_code=404, detail=f"{project} or {version_group} not found"
            )
        if result == None:
            return {"error": "Version not found."}
        return {
            "project_id": project,
            "project_name": result[0][1],
            "version_group": version_group,
            "versions": [res[0] for res in result],
        }


@app.get(
    "/projects/{project}/version_group/{version_group}/builds",
    description="get builds by version_group",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "project_id": "leaves",
                        "project_name": "leaves",
                        "version_group": "1.20",
                        "builds": [
                            {
                                "build": 1,
                                "time": "2023-06-10T16:23:18.000Z",
                                "channel": "experimental",
                                "promoted": False,
                                "changes": [],
                                "downloads": {
                                    "application": {
                                        "name": "leaves-1.20.jar",
                                        "sha256": "75201e1ebfaeb58715c08c2475db2ad24c3e75d2ec325de43f98b40ec5f819aa",
                                        "url": "https://github.com/LeavesMC/Leaves/releases/download/1.20-1fbd584/leaves-1.20.jar",
                                    }
                                },
                            }
                        ],
                    }
                }
            },
        }
    },
)
@api_json_middleware
async def version_group_builds_info(
    project: str = "leaves", version_group: str = "1.20"
):
    with Session(bind=app.state.sql_engine) as sess:
        build_result = (
            sess.query(Project)
            .filter(
                Project.project_id == project, Project.version_group == version_group
            )
            .all()
        )
        if len(build_result) == 0:
            raise HTTPException(
                status_code=404, detail=f"{project} or {version_group} not found"
            )
        download_result = (
            sess.query(File)
            .filter(File.project_id == project, File.version_group == version_group)
            .all()
        )
        download_info_by_build = {}
        for download_info in download_result:
            if download_info_by_build.get(download_info.build) is None:  # 3 is build
                download_info_by_build[download_info.build] = {}
            download_info_by_build[download_info.build][download_info.type] = {
                "name": download_info.name,
                "sha256": download_info.sha256,
                "url": download_info.url,
            }

        change_result = (
            sess.query(Commit)
            .filter(Commit.project_id == project, Commit.version_group == version_group)
            .all()
        )
        commit_info_by_build = {}
        for commit_info in change_result:
            if commit_info_by_build.get(commit_info.build) is None:  # 3 is build
                commit_info_by_build[commit_info.build] = []
            commit_info_by_build[commit_info.build].append(
                {
                    "commit": commit_info.hash,
                    "summary": commit_info.summary,
                    "message": commit_info.message,
                }
            )

        builds = []
        for build in build_result:
            builds.append(
                {
                    "build": build.build,
                    "time": build.time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                    "channel": build.channel,
                    "promoted": build.promoted,
                    "changes": commit_info_by_build[build.build]
                    if build.build in commit_info_by_build
                    else [],
                    "downloads": download_info_by_build[build.build]
                    if build.build in download_info_by_build
                    else [],
                }
            )

        return {
            "project_id": project,
            "project_name": project,
            "version_group": version_group,
            "builds": builds,
        }


@app.get(
    "/projects/{project}/versions/{version}/builds/downloads/latest",
    description="get latest build info",
)
async def latest_build_info(project: str = "leaves", version: str = "1.20.1"):
    with Session(bind=app.state.sql_engine) as sess:
        download_result = (
            sess.query(File.url)
            .filter(
                File.project_id == project,
                File.version == version,
            )
            .order_by(desc(File.build))
            .limit(1)
            .one_or_none()
        )
        if download_result == None:
            raise HTTPException(
                status_code=404, detail=f"{project} or {version} not found"
            )
        return RedirectResponse(url=download_result[0])


@app.get(
    "/projects/{project}/versions/{version}/builds/{build}/downloads/{name}",
    description="download file by name",
)
@api_json_middleware
async def download_file_by_name(
    build: int, name: str, project: str = "leaves", version: str = "1.20.1"
):
    with Session(bind=app.state.sql_engine) as sess:
        download_result = (
            sess.query(File.url)
            .filter(
                File.project_id == project,
                File.version == version,
                File.build == build,
                File.name == name,
            )
            .one_or_none()
        )
        if download_result == None:
            raise HTTPException(
                status_code=404, detail=f"{project} or {version} or {build} not found"
            )
        return RedirectResponse(url=download_result[0])


class ReleaseData(BaseModel):
    project_id: str = "leaves"
    project_name: str = "leaves"
    version: str
    time: str
    channel: str = "default"
    promoted: bool = False
    changes: str
    downloads: dict
    secret: str


@app.post("/new_release", include_in_schema=False)
@api_json_middleware
async def new_release(data: ReleaseData):
    if data.secret != SECRET:
        return Response(status_code=403)
    with Session(bind=app.state.sql_engine) as sess:
        data.time = data.time.replace("T", " ").replace("Z", "")
        build = (
            sess.query(func.max(Project.build))
            .where(Project.version_group == data.version[:4])
            .where(Project.project_id == data.project_id)
            .one_or_none()[0]
            + 1
        )
        sql_replace(
            sess,
            Project,
            project_id=data.project_id,
            project_name=data.project_name,
            version=data.version,
            version_group=data.version[:4],
            time=data.time,
            channel=data.channel,
            promoted=data.promoted,
            build=build,
        )
        sql_replace(
            sess,
            File,
            sha256=data.downloads["application"]["sha256"],
            type="application",
            name=data.downloads["application"]["name"],
            build=build,
            version=data.version,
            version_group=data.version[:4],
            project_id=data.project_id,
            url=data.downloads["application"]["url"],
        )
        if data.changes != "":
            commits = [
                {
                    "commit": commit.split("<<<")[0],
                    "summary": commit.split("<<<")[1],
                    "message": commit.split("<<<")[1],
                }
                for commit in data.changes.split(">>>")[:-1]
            ]
            for commit in commits:
                sql_replace(
                    sess,
                    Commit,
                    hash=commit["commit"],
                    summary=commit["summary"],
                    message=commit["message"],
                    build=build,
                    version=data.version,
                    version_group=data.version[:4],
                    project_id=data.project_id,
                )
        sess.commit()


async def refresh_cdn(path: str):
    client = Client(
        {
            "public_key": CDNConfig.public_key,
            "private_key": CDNConfig.private_key,
            "base_url": "https://api.ucloud.cn",
        }
    )

    try:
        client.ucdn().refresh_new_ucdn_domain_cache(
            {"Type": "file", "UrlList": [f"{CDN_URL}{path}"]}
        )
    except exc.UCloudException as e:
        print(e)


@app.post("/upload_file", include_in_schema=False)
@api_json_middleware
async def upload_file(
    file: UploadFile = File(),
    secret: str = Form(),
    filename: str = Form(),
    filehash: str = Form(),
):
    if secret != SECRET:
        return Response(status_code=403)
    with open(os.path.join("cache", filename), "wb") as f:
        f.write(await file.read())
    # with open(os.path.join("cache", filename), "rb") as f:
    # 直接读 body
    await file.seek(0)
    sha256_obj = hashlib.sha256()
    while True:
        data = await file.read(65536)  # 一次读取64KB的数据
        if not data:
            break
        sha256_obj.update(data)
    hash = sha256_obj.hexdigest()
    if hash == str(filehash):
        await refresh_cdn("/cache/" + filename)
        return CDN_URL + "/cache/" + filename
    else:
        return f"Hash Error {hash}"


if __name__ == "__main__":
    WebConfig.load()
    CDNConfig.load()
    host, port = WebConfig.host, WebConfig.port
    uvicorn.run(app, host=host, port=port)
