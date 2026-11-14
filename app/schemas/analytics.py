from pydantic import BaseModel


class PlatformAnalytics(BaseModel):
    platform_id: str
    total_conversations: int
    total_messages: int
    total_learners: int
    page_type_distribution: dict[str, int]
    ai_provider_usage: dict[str, int]
    language_breakdown: dict[str, int]
    support_tickets_count: int


class TeacherAnalytics(BaseModel):
    course_id: str
    course_title: str
    total_questions: int
    frequent_topics: list[str]
    difficult_concepts_flagged: list[str]
