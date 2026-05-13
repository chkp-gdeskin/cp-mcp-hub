from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EnvVarDef(BaseModel):
    name: str
    label: str
    type: Literal["string", "password", "boolean", "enum", "url", "integer"] = "string"
    required: bool = False
    secret: bool = False
    description: str = ""
    default: str | None = None
    options: list[str] | None = None


class CliArgDef(BaseModel):
    name: str
    description: str = ""
    default: str | None = None
    required: bool = False


class ServerDefinition(BaseModel):
    id: str
    display_name: str
    npm_package: str
    description: str = ""
    doc_url: str = ""
    icon: str = "shield"
    env_vars: list[EnvVarDef] = Field(default_factory=list)
    cli_args: list[CliArgDef] = Field(default_factory=list)


class Manifest(BaseModel):
    version: str
    generated_at: str
    source_commit: str
    servers: list[ServerDefinition]
