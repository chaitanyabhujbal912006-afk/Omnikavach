import os
from supabase import create_client, Client
from langchain_huggingface import HuggingFaceEmbeddings
from dotenv import load_dotenv

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


def retrieve_guidelines(query_text, top_k=2):
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


if __name__ == "__main__":
    # These are the exact medical rules required to solve the hackathon problem statement
    medical_rules = [
        "Sepsis-3 Criteria: Sepsis should be defined as life-threatening organ dysfunction caused by a dysregulated host response to infection. Clinical criteria include an acute change in total SOFA score greater than 2 points.",
        "Hyperlactatemia in Sepsis: A serum lactate level greater than 2 mmol/L is associated with highly severe disease and indicates tissue hypoperfusion. Levels above 4 mmol/L require immediate aggressive fluid resuscitation.",
        "Erroneous Lab Results: A sudden, isolated drop in White Blood Cell count (WBC < 1.0) paired with a massive spike in Creatinine, in the absence of matching vitals or physical symptoms, strongly suggests a mislabeled sample or machine calibration error. A redraw is mandatory before clinical intervention.",
    ]

    # 1. We already ingested, so comment this out!
    # ingest_guidelines(medical_rules, "ICU_Critical_Care_Guidelines_2026")

    # 2. Test the retrieval!
    test_question = "The patient's lactate level just hit 4.5. What should we do?"
    retrieve_guidelines(test_question)
