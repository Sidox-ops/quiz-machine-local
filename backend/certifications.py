from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class LocalCertification:
    code: str
    title: str
    study_guide_url: str
    domains: tuple[str, ...]

    def public_dict(self) -> dict:
        value = asdict(self)
        value["domains"] = list(self.domains)
        return value


CERTIFICATIONS = (
    LocalCertification(
        code="AI-901",
        title="Microsoft Azure AI Fundamentals",
        study_guide_url=(
            "https://learn.microsoft.com/credentials/certifications/"
            "resources/study-guides/ai-901"
        ),
        domains=(
            "Identify AI concepts and capabilities",
            "Implement AI solutions by using Microsoft Foundry",
        ),
    ),
    LocalCertification(
        code="AI-103",
        title="Developing AI Apps and Agents on Azure",
        study_guide_url=(
            "https://learn.microsoft.com/credentials/certifications/"
            "resources/study-guides/ai-103"
        ),
        domains=(
            "Plan and manage an Azure AI solution",
            "Implement generative AI and agentic solutions",
            "Implement computer vision solutions",
            "Implement text analysis solutions",
            "Implement information extraction solutions",
        ),
    ),
    LocalCertification(
        code="AI-200",
        title="Developing AI Cloud Solutions on Azure",
        study_guide_url=(
            "https://learn.microsoft.com/credentials/certifications/"
            "resources/study-guides/ai-200"
        ),
        domains=(
            "Develop containerized solutions on Azure",
            "Develop AI solutions by using Azure data management services",
            "Connect to and consume Azure services",
            "Secure, monitor, and troubleshoot Azure solutions",
        ),
    ),
    LocalCertification(
        code="AI-300",
        title="Operationalizing Machine Learning and Generative AI Solutions",
        study_guide_url=(
            "https://learn.microsoft.com/credentials/certifications/"
            "resources/study-guides/ai-300"
        ),
        domains=(
            "Design and implement an MLOps infrastructure",
            "Implement machine learning model lifecycle and operations",
            "Design and implement a GenAIOps infrastructure",
            "Implement generative AI quality assurance and observability",
            "Optimize generative AI systems and model performance",
        ),
    ),
    LocalCertification(
        code="AI-500",
        title="Designing and Implementing Multi-Agent AI Solutions",
        study_guide_url=(
            "https://learn.microsoft.com/credentials/certifications/"
            "resources/study-guides/ai-500"
        ),
        domains=(
            "Architect multi-agent solutions",
            "Develop multi-agent solutions in Azure",
            "Evaluate, optimize, and monitor multi-agent solutions",
            "Secure, govern, and deploy multi-agent solutions",
        ),
    ),
)

_BY_CODE = {item.code: item for item in CERTIFICATIONS}


def certification(code: str) -> LocalCertification:
    normalized = code.strip().upper()
    try:
        return _BY_CODE[normalized]
    except KeyError as error:
        raise ValueError(f"Unsupported certification: {normalized or code}") from error


def public_certifications() -> list[dict]:
    return [item.public_dict() for item in CERTIFICATIONS]
