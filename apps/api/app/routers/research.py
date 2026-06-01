from fastapi import APIRouter

from app.services.topic_research import TopicResearchRequest, TopicResearchResponse, research_topics

router = APIRouter()


@router.post("/topics")
def research_topic_ideas(request: TopicResearchRequest) -> TopicResearchResponse:
    return research_topics(request)
