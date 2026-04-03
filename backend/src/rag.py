import os
from supabase import create_client, Client
from langchain_huggingface import HuggingFaceEmbeddings
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 1. Load the secret keys from your .env file
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# 2. Connect to your Supabase database
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 3. Load the AI Embedding Model (this runs locally and is free/fast)
print("Loading AI Embedding model (this might take a few seconds the first time)...")
embeddings_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")


def ingest_guidelines(text_chunks, source_name):
    print(f"Ingesting {len(text_chunks)} medical guidelines into Supabase...")

    # Turn the text into math vectors
    embeddings = embeddings_model.embed_documents(text_chunks)

    # Prepare the data packet
    data_to_insert = []
    for i in range(len(text_chunks)):
        data_to_insert.append(
            {
                "content": text_chunks[i],
                "metadata": {"source": source_name, "chunk_index": i},
                "embedding": embeddings[i],
            }
        )

    # Push to Supabase
    supabase.table("medical_guidelines").insert(data_to_insert).execute()
    print("SUCCESS: Ingestion complete! Your AI Librarian has memorized the rules.")


def retrieve_guidelines(query_text, top_k=3):
    print(f"\nSearching AI Librarian for: '{query_text}'")
    
    # 1. Turn the doctor's question into a math vector
    query_vector = embeddings_model.embed_query(query_text)
    
    # 2. Ask Supabase to find the closest matches using that SQL function we built earlier
    response = supabase.rpc(
        "match_guidelines",
        {
            "query_embedding": query_vector,
            "match_threshold": 0.1, # Must be at least 10% relevant
            "match_count": top_k
        }
    ).execute()
    
    # 3. Clean up the results to hand to the Chief Agent
    results = response.data
    if not results:
        print("No relevant guidelines found.")
        return []
        
    for idx, row in enumerate(results):
        print(f"\n--- Rule Found (Match Score: {round(row['similarity']*100)}%) ---")
        print(row['content'])
        
    return [row['content'] for row in results]


def search_medical_guidelines(query_text):
    """Tool-ready retrieval function for the Chief Agent.
    Example query: 'signs of early sepsis'
    Returns: top 3 matching guideline text chunks.
    """
    return retrieve_guidelines(query_text=query_text, top_k=3)


def ingest_file(file_path):
    print(f"Loading document: {file_path}")
    
    # 1. Check if it's a PDF or TXT and load it
    if file_path.endswith('.pdf'):
        loader = PyPDFLoader(file_path)
    elif file_path.endswith('.txt'):
        loader = TextLoader(file_path)
    else:
        print("Unsupported file type. Please use .pdf or .txt")
        return
        
    documents = loader.load()
    
    # 2. Chunk the document (Break it into readable paragraphs for the AI)
    # chunk_size: How many characters per chunk (500 is good for medical rules)
    # chunk_overlap: Keep some context between chunks so sentences aren't cut in half
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500, 
        chunk_overlap=50
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Document split into {len(chunks)} chunks.")
    
    # 3. Extract the text and upload using your existing logic!
    text_chunks = [chunk.page_content for chunk in chunks]
    source_name = os.path.basename(file_path)
    
    # Call your existing ingestion function
    ingest_guidelines(text_chunks, source_name)


if __name__ == "__main__":
    # Test the real file ingestion!
    # Make sure to point this to where your text file actually is
    test_file_path = "data/guidelines.txt"
    ingest_file(test_file_path)
    
    # You can comment out the retrieval test for now while you ingest
    # retrieve_guidelines("The patient's lactate level just hit 4.5. What should we do?")
