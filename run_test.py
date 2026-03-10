import os
from app import create_app
from extensions import db
from models import KnowledgeDocument, PersonaKnowledgeBase, DocumentChunk
from tasks import process_document_async

app = create_app()
with app.app_context():
    kb = PersonaKnowledgeBase.query.first()
    if not kb:
        print("No active persona knowledge base available.")
        exit(1)

    file_path = os.path.abspath('test_doc.txt')
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write('테스트 입력 텍스트입니다. 인공지능이 문맥을 잘 파악하여 문서를 인덱싱하는 것은 매우 중요합니다.')

    doc = KnowledgeDocument(
        knowledge_base_id=kb.id,
        filename='test_doc.txt',
        original_filename='test_doc.txt',
        file_path=file_path,
        file_type='txt',
        file_size=os.path.getsize(file_path),
        processing_status='pending'
    )
    db.session.add(doc)
    db.session.commit()

    print(f'\n--- Starting Task for Doc ID {doc.id} ---')
    try:
        process_document_async.apply(args=(doc.id,)).get()
    except Exception as e:
        print(f"Error executing task: {e}")
        
    chunks = DocumentChunk.query.filter_by(document_id=doc.id).all()
    print(f'\n--- Resulting Chunks ({len(chunks)}) ---')
    for c in chunks:
        print(f'Metadata: {c.chunk_metadata}')
