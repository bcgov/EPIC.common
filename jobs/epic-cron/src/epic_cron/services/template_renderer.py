"""Rendering service for packaged email templates."""
from typing import Optional

from jinja2 import TemplateNotFound
from jinja2 import Environment, PackageLoader, select_autoescape

from epic_cron.data_classes.email_details import EmailDetails


class TemplateRenderer:
    """Render email templates from packaged resources."""

    _env = Environment(
        loader=PackageLoader("epic_cron", "templates"),
        autoescape=select_autoescape(("html", "xml")),
    )

    @classmethod
    def render(cls, template_name: str, body_args: Optional[dict], domain: str) -> str:
        """Render a packaged template from the domain namespace."""
        template_path = f"{domain}/{template_name}"
        try:
            template = cls._env.get_template(template_path)
        except TemplateNotFound as exc:
            raise ValueError(
                f"Template '{template_name}' was not found for domain '{domain}'."
            ) from exc
        return template.render(body_args or {})

    @staticmethod
    def _inject_environment_banner(rendered_body: str, environment: str) -> str:
        """Add environment banner to non-production emails."""
        env_message = (
            '<div style="background-color: #fff3cd; border: 1px solid #ffc107; '
            'padding: 10px; margin: 20px 0; text-align: center; font-size: 14px; '
            f'color: #856404;"><strong>You are using {environment} environment</strong></div>'
        )
        if "</body>" in rendered_body:
            return rendered_body.replace("</body>", f"{env_message}</body>")
        return rendered_body + env_message

    @classmethod
    def compose_email(
        cls,
        email_details: EmailDetails,
        domain: str,
        web_url: str,
        environment: str = "",
    ) -> EmailDetails:
        """Return a transport-ready email with rendered HTML body."""
        body_args = dict(email_details.body_args or {})
        body_args["logo_url"] = f"{web_url}/assets/EAO_Logo-BZOR9oRj.png"
        rendered_body = cls.render(email_details.template_name, body_args, domain)

        if environment and environment.lower() != "production":
            rendered_body = cls._inject_environment_banner(rendered_body, environment)

        return EmailDetails(
            sender=email_details.sender,
            recipients=email_details.recipients,
            subject=email_details.subject,
            body=rendered_body,
            body_type="html",
            cc=email_details.cc,
            bcc=email_details.bcc,
        )
