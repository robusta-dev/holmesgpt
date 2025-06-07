from pydantic import BaseModel


class KubectlImageConfig(BaseModel):
    image: str
    allowed_commands: list[str]


class KubectlConfig(BaseModel):
    allowed_images: list[KubectlImageConfig] = []


class BashExecutorConfig(BaseModel):
    kubectl: KubectlConfig = KubectlConfig()
