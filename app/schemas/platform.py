from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ThemeConfig(BaseModel):
    primary: str = "#16A34A"
    secondary: str = "#14532D"
    background: str = "#FFFFFF"
    text: str = "#111827"
    chat_button: str = "#16A34A"


class BrandingConfig(BaseModel):
    logo_url: str = "https://bridgemate.example.com/logo.png"


class FeaturesConfig(BaseModel):
    voice: bool = True
    human_support: bool = True
    simple_mode: bool = True
    job_assistance: bool = True
    course_assistant: bool = True


class PluginConfigResponse(BaseModel):
    platform_name: str
    theme: ThemeConfig
    branding: BrandingConfig
    welcome_message: str
    language: str = "en"
    position: str = "bottom-right"
    size: str = "medium"
    features: FeaturesConfig
    context_extraction_rules: dict[str, Any] = Field(default_factory=dict)
    public_key: str


class PluginConfigUpdate(BaseModel):
    platform_name: str | None = None
    theme: ThemeConfig | None = None
    branding: BrandingConfig | None = None
    welcome_message: str | None = None
    language: str | None = None
    position: str | None = None
    size: str | None = None
    features: FeaturesConfig | None = None
    context_extraction_rules: dict[str, Any] | None = None


class PlatformCreate(BaseModel):
    name: str = Field(..., examples=["Savanna LMS"])
    domain: str = Field(..., examples=["savanna.example.com"])
    allowed_domains: list[str] | None = Field(default_factory=list)
    initial_config: PluginConfigUpdate | None = None


class PlatformResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    domain: str
    public_key: str
    enabled: bool
    domains: list[str] = Field(default_factory=list)
    configuration: PluginConfigResponse | None = None


class PlatformRegistrationResult(PlatformResponse):
    secret_key: str  # Only returned once upon creation!


class IntegrationVerifyRequest(BaseModel):
    public_key: str
    secret_key: str
    domain: str


class IntegrationVerifyResponse(BaseModel):
    verified: bool
    platform_id: str
    platform_name: str
    message: str
