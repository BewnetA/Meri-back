from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_session_context
from app.models.course import Course, Document, DocumentChunk
from app.schemas.course import (
    CourseCreate,
    CourseResponse,
    DocumentResponse,
    KnowledgeChunkResult,
    KnowledgeSearchRequest,
)
from app.services.ai.embeddings import get_embedding
from app.services.document_parser import document_parser

router = APIRouter()


@router.get("/courses", response_model=list[CourseResponse])
async def list_courses(
    session: dict = Depends(get_session_context),
    db: AsyncSession = Depends(get_db),
):
    platform_id = session.get("platform_id")
    stmt = select(Course)
    if platform_id:
        stmt = stmt.where(Course.platform_id == platform_id, Course.is_active == True)
    res = await db.execute(stmt)
    return res.scalars().all()


@router.post("/courses", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course(
    payload: CourseCreate,
    session: dict = Depends(get_session_context),
    db: AsyncSession = Depends(get_db),
):
    platform_id = session.get("platform_id")
    if not platform_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Platform identification required. Provide integration token or X-Public-Key header.",
        )

    course = Course(
        platform_id=platform_id,
        course_code=payload.course_code,
        title=payload.title,
        description=payload.description,
        instructor_name=payload.instructor_name,
        is_active=True,
    )
    db.add(course)
    await db.commit()
    await db.refresh(course)
    return course


@router.get("/courses/{id}", response_model=CourseResponse)
async def get_course_detail(
    id: str,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Course).where(Course.id == id)
    res = await db.execute(stmt)
    course = res.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    return course


@router.post("/knowledge/documents", response_model=DocumentResponse)
async def upload_knowledge_document(
    course_id: str = Form(...),
    title: str = Form(...),
    file: UploadFile = File(...),
    session: dict = Depends(get_session_context),
    db: AsyncSession = Depends(get_db),
):
    """Uploads institutional learning material (PDF, DOCX, TXT, HTML) to knowledge base."""
    # Validate course
    course_res = await db.execute(select(Course).where(Course.id == course_id))
    course = course_res.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    platform_id = course.platform_id
    contents = await file.read()
    file_size = len(contents)

    filename = file.filename or "document.txt"
    ext = filename.split(".")[-1].lower() if "." in filename else "txt"
    if ext not in ["pdf", "docx", "txt", "html"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Supported formats: PDF, DOCX, TXT, HTML",
        )

    doc = Document(
        course_id=course.id,
        platform_id=platform_id,
        title=title,
        file_type=ext,
        file_path=filename,
        file_size=file_size,
        is_processed=False,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Automatically trigger processing pipeline
    chunks_data = []
    if ext == "pdf":
        chunks_data = document_parser.parse_pdf(contents)
    elif ext == "docx":
        chunks_data = document_parser.parse_docx(contents)
    elif ext == "html":
        chunks_data = document_parser.parse_html(contents.decode("utf-8", errors="ignore"))
    else:
        chunks_data = document_parser.parse_txt(contents.decode("utf-8", errors="ignore"))

    for c in chunks_data:
        embedding = await get_embedding(c["content"])
        chunk_obj = DocumentChunk(
            document_id=doc.id,
            course_id=course.id,
            platform_id=platform_id,
            chunk_index=c["chunk_index"],
            content=c["content"],
            page_number=c.get("page_number"),
            section_title=c.get("section_title"),
            embedding=embedding,
            metadata_json={"title": title, "course_code": course.course_code},
        )
        db.add(chunk_obj)

    doc.is_processed = True
    doc.chunk_count = len(chunks_data)
    await db.commit()
    await db.refresh(doc)

    return doc


@router.post("/knowledge/documents/{id}/process")
async def process_document_manually(
    id: str,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Document).where(Document.id == id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    return {"status": "success", "chunk_count": doc.chunk_count, "is_processed": doc.is_processed}


@router.get("/knowledge/documents", response_model=list[DocumentResponse])
async def list_documents(
    course_id: str | None = None,
    session: dict = Depends(get_session_context),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Document)
    platform_id = session.get("platform_id")
    if platform_id:
        stmt = stmt.where(Document.platform_id == platform_id)
    if course_id:
        stmt = stmt.where(Document.course_id == course_id)
    res = await db.execute(stmt)
    return res.scalars().all()


@router.post("/knowledge/search", response_model=list[KnowledgeChunkResult])
async def search_knowledge_base(
    payload: KnowledgeSearchRequest,
    session: dict = Depends(get_session_context),
    db: AsyncSession = Depends(get_db),
):
    """Executes vector similarity search over authorized institutional material."""
    from app.services.course_assistant import course_assistant_service

    platform_id = session.get("platform_id")
    if not platform_id:
        # Search all if demo/dev without platform
        plat_res = await db.execute(select(Course.platform_id).limit(1))
        platform_id = plat_res.scalar_one_or_none() or ""

    results = await course_assistant_service.retrieve_relevant_chunks(
        db=db,
        platform_id=platform_id,
        query=payload.query,
        course_id=payload.course_id,
        top_k=payload.top_k,
    )

    return [
        KnowledgeChunkResult(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            document_title=doc_title,
            content=chunk.content,
            page_number=chunk.page_number,
            section_title=chunk.section_title,
            score=round(score, 4),
        )
        for chunk, doc_title, score in results
    ]
