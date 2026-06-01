import json

from openai import OpenAI, OpenAIError
from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings


class TopicResearchRequest(BaseModel):
    niche: str
    audience: str
    goal: str


class TopicIdea(BaseModel):
    id: str
    title: str
    hook: str
    angle: str
    image_prompt: str
    negative_prompt: str
    motion_prompt: str
    narration: str
    style: str
    aspect_ratio: str
    image_option_count: int = Field(ge=1, le=4)


class TopicResearchResponse(BaseModel):
    provider: str
    ideas: list[TopicIdea]


class OpenAITopicResearchUnavailable(RuntimeError):
    pass


def research_topics(request: TopicResearchRequest) -> TopicResearchResponse:
    if not settings.openai_api_key:
        return TopicResearchResponse(
            provider="mock-topic-research",
            ideas=build_mock_topic_ideas(request),
        )

    try:
        return research_topics_with_openai(request)
    except (OpenAITopicResearchUnavailable, OpenAIError, ValidationError, json.JSONDecodeError):
        return TopicResearchResponse(
            provider="mock-topic-research",
            ideas=build_mock_topic_ideas(request),
        )


def research_topics_with_openai(request: TopicResearchRequest) -> TopicResearchResponse:
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=settings.openai_topic_model,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "Return JSON only. Create exactly 3 short-form video topic ideas. "
                    "Use these keys: ideas[].id,title,hook,angle,image_prompt,negative_prompt,"
                    "motion_prompt,narration,style,aspect_ratio,image_option_count. "
                    "style must be one of Cinematic, Photographic, Design, Animation, Realistic. "
                    "aspect_ratio must be 9:16, 1:1, or 16:9. image_option_count must be 1-4."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Niche: {clean_topic_input(request.niche, 'AI video creation')}\n"
                    f"Audience: {clean_topic_input(request.audience, 'busy creators')}\n"
                    f"Goal: {clean_topic_input(request.goal, 'help them make better short videos')}"
                ),
            },
        ],
    )

    content = response.choices[0].message.content
    if not content:
        raise OpenAITopicResearchUnavailable("OpenAI topic response was empty")

    parsed = json.loads(content)
    ideas = [TopicIdea.model_validate(idea) for idea in parsed.get("ideas", [])]
    if len(ideas) != 3:
        raise OpenAITopicResearchUnavailable("OpenAI topic response did not include 3 ideas")
    return TopicResearchResponse(provider="openai", ideas=ideas)


def build_mock_topic_ideas(request: TopicResearchRequest) -> list[TopicIdea]:
    niche = clean_topic_input(request.niche, "AI video creation")
    audience = clean_topic_input(request.audience, "busy creators")
    goal = clean_topic_input(request.goal, "help them make better short videos")

    return [
        TopicIdea(
            id=f"myth-{slugify_topic(niche)}",
            title=f"The biggest myth about {niche}",
            hook=f"The biggest myth about {niche}",
            angle=f"Myth-busting angle for {audience}.",
            image_prompt=(
                "a split-screen myth versus reality explainer scene "
                f"about {niche} for {audience}, modern creator education style, "
                "polished social video thumbnail"
            ),
            negative_prompt="tiny unreadable text, watermark, cluttered layout, distorted hands",
            motion_prompt=(
                "Smooth side-by-side reveal, gentle emphasis pulses, stable camera, "
                "optimized for a short hook video"
            ),
            narration=(
                f"Most people get this wrong: {niche}. In the next few seconds, "
                f"I’ll show {audience} how to {goal}."
            ),
            style="Photographic",
            aspect_ratio="9:16",
            image_option_count=3,
        ),
        TopicIdea(
            id=f"mistakes-{slugify_topic(niche)}",
            title=f"3 mistakes people make with {niche}",
            hook=f"3 mistakes people make with {niche}",
            angle=f"Common mistakes angle for {audience}.",
            image_prompt=(
                "three clean mistake cards floating around a central creator workstation "
                f"about {niche} for {audience}, modern creator education style, "
                "polished social video thumbnail"
            ),
            negative_prompt="tiny unreadable text, watermark, cluttered layout, distorted hands",
            motion_prompt=(
                "Cards slide in one by one, subtle camera push, clear readable composition, "
                "optimized for a short explainer video"
            ),
            narration=(
                f"Here are three mistakes to avoid when working on {niche}. "
                f"In the next few seconds, I’ll show {audience} how to {goal}."
            ),
            style="Design",
            aspect_ratio="9:16",
            image_option_count=3,
        ),
        TopicIdea(
            id=f"workflow-{slugify_topic(niche)}",
            title=f"A simple workflow for {niche}",
            hook=f"A simple workflow for {niche}",
            angle=f"Simple workflow angle for {audience}.",
            image_prompt=(
                "a clean step-by-step workflow board with bright connected icons "
                f"about {niche} for {audience}, modern creator education style, "
                "polished social video thumbnail"
            ),
            negative_prompt="tiny unreadable text, watermark, cluttered layout, distorted hands",
            motion_prompt=(
                "Camera pans across each step, icons drift gently, calm tutorial pacing, "
                "optimized for a short explainer video"
            ),
            narration=(
                f"Use this simple workflow next time you need {niche}. "
                f"In the next few seconds, I’ll show {audience} how to {goal}."
            ),
            style="Design",
            aspect_ratio="9:16",
            image_option_count=3,
        ),
    ]


def clean_topic_input(value: str, fallback: str) -> str:
    cleaned = " ".join(value.strip().split())
    return cleaned or fallback


def slugify_topic(value: str) -> str:
    slug = "".join(character.lower() if character.isalnum() else "-" for character in value)
    collapsed = "-".join(part for part in slug.split("-") if part)
    return collapsed or "topic"
