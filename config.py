import json
import os


def checktyp(obj: object, typ: type):
    assert isinstance(obj, typ)
    return obj


class MysqlConfig:
    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "username"
    password: str = "password"
    database: str = "database"

    @classmethod
    def to_dict(cls):
        return {
            "host": cls.host,
            "port": cls.port,
            "user": cls.user,
            "password": cls.password,
            "database": cls.database,
        }

    @classmethod
    def save(cls, target="./config/mysql.config.json"):
        os.makedirs("config", exist_ok=True)
        with open(target, "w") as fd:
            json.dump(cls.to_dict(), fd)

    @classmethod
    def load(cls, target="./config/mysql.config.json"):
        if not os.path.exists(target):
            cls.save(target=target)
            return
        data: dict
        with open(target, "r") as fd:
            data = json.load(fd)
        cls.host = checktyp(data.get("host"), str)
        cls.port = checktyp(data.get("port"), int)
        cls.user = checktyp(data.get("user"), str)
        cls.password = checktyp(data.get("password"), str)
        cls.database = checktyp(data.get("database"), str)

class WebConfig:
    host: str = "0.0.0.0"
    port: int = 8000

    @classmethod
    def to_dict(cls):
        return {
            "host": cls.host,
            "port": cls.port,
        }

    @classmethod
    def save(cls, target="./config/web.config.json"):
        os.makedirs("config", exist_ok=True)
        with open(target, "w") as fd:
            json.dump(cls.to_dict(), fd)

    @classmethod
    def load(cls, target="./config/web.config.json"):
        if not os.path.exists(target):
            cls.save(target=target)
            return
        data: dict
        with open(target, "r") as fd:
            data = json.load(fd)
        cls.host = checktyp(data.get("host"), str)
        cls.port = checktyp(data.get("port"), int)

class CDNConfig:
    private_key: str = ""
    public_key: str = ""

    @classmethod
    def to_dict(cls):
        return {
            "private_key": cls.private_key,
            "public_key": cls.public_key,
        }

    @classmethod
    def save(cls, target="./config/cdn.config.json"):
        os.makedirs("config", exist_ok=True)
        with open(target, "w") as fd:
            json.dump(cls.to_dict(), fd)

    @classmethod
    def load(cls, target="./config/cdn.config.json"):
        if not os.path.exists(target):
            cls.save(target=target)
            return
        data: dict
        with open(target, "r") as fd:
            data = json.load(fd)
        cls.private_key = checktyp(data.get("private_key"), str)
        cls.public_key = checktyp(data.get("public_key"), str)