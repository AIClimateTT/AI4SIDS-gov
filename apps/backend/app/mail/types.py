from dataclasses import dataclass, field


@dataclass
class EmailTemplate:
    id: str
    variables: dict[str, object] = field(default_factory=dict)


@dataclass
class SendEmailRequest:
    to: list[str]
    subject: str
    text: str = ""
    html: str = ""
    from_address: str = ""
    template: EmailTemplate | None = None


@dataclass
class SendEmailResponse:
    id: str
