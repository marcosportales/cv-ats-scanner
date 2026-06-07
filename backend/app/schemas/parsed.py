from pydantic import BaseModel, ConfigDict, Field


class ContactInfo(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None
    professional_links_level: str | None = None  # ok | mention_only | missing
    professional_link_mentions: list[str] = Field(default_factory=list)


class ExperienceItem(BaseModel):
    company: str | None = None
    role: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    bullets: list[str] = Field(default_factory=list)
    skills_mentioned: list[str] = Field(default_factory=list)


class EducationItem(BaseModel):
    degree: str | None = None
    institution: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    field_of_study: str | None = None


class ProjectItem(BaseModel):
    name: str | None = None
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)
    url: str | None = None


class SkillsBlock(BaseModel):
    hard: list[str] = Field(default_factory=list)
    soft: list[str] = Field(default_factory=list)


class LanguageItem(BaseModel):
    name: str
    level: str | None = None


class ParsedResume(BaseModel):
    # 1.1: education/projects now typed (EducationItem/ProjectItem) instead of list[dict]
    schema_version: str = "1.1"
    language: str = "es"
    contact: ContactInfo = Field(default_factory=ContactInfo)
    sections_detected: list[str] = Field(default_factory=list)
    summary: str | None = None
    experience: list[ExperienceItem] = Field(default_factory=list)
    skills: SkillsBlock = Field(default_factory=SkillsBlock)
    education: list[EducationItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    languages: list[LanguageItem] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    evidence_skills: list[str] = Field(default_factory=list)
    parse_confidence: float = 0.5

    model_config = ConfigDict(extra="forbid")


class JobRequirements(BaseModel):
    must: list[str] = Field(default_factory=list)
    nice: list[str] = Field(default_factory=list)


class KeywordCategories(BaseModel):
    technical_required: list[str] = Field(default_factory=list)
    technical_optional: list[str] = Field(default_factory=list)
    contextual: list[str] = Field(default_factory=list)
    language: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)


class ParsedJob(BaseModel):
    schema_version: str = "1.0"
    title: str | None = None
    seniority: str | None = None
    modality: str | None = None
    location: str | None = None
    hard_skills: list[str] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    requirements: JobRequirements = Field(default_factory=JobRequirements)
    responsibilities: list[str] = Field(default_factory=list)
    languages: list[LanguageItem] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    keyword_categories: KeywordCategories = Field(default_factory=KeywordCategories)

    model_config = ConfigDict(extra="forbid")


class ScoreCategories(BaseModel):
    ats_parseability: float = 0
    structure: float = 0
    contact_info: float = 0
    keywords: float = 0
    job_match: float = 0
    writing_quality: float = 0
    risk_penalties: float = 0


class AnalysisResult(BaseModel):
    total_score: float
    ats_score: float
    job_match_score: float
    level: str
    summary: str
    scoring_version: str = "1.2.0"
    categories: ScoreCategories
    found_keywords: list[dict] = Field(default_factory=list)
    missing_keywords: list[dict] = Field(default_factory=list)
    missing_contextual_keywords: list[dict] = Field(default_factory=list)
    missing_education_keywords: list[dict] = Field(default_factory=list)
    keyword_gaps: dict[str, list[dict]] = Field(default_factory=dict)
    language_gaps: list[dict] = Field(default_factory=list)
    detection_evidence: list[dict] = Field(default_factory=list)
    requirements_coverage: list[dict] = Field(default_factory=list)
    critical_issues: list[dict] = Field(default_factory=list)
    matches: dict = Field(default_factory=dict)
    recommendations_available: bool = False

    model_config = ConfigDict(extra="forbid")
