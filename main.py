# First, I load PDFs and convert them into documents.
# Then I split them into chunks and convert them into embeddings.
# These embeddings are stored in FAISS for fast retrieval.

# When a user requests a report, the system retrieves relevant chunks,
# combines them into context, and sends them to an LLM using a structured prompt.
# The LLM then generates a professional DDR report.


import os
import streamlit as st

# Loads PDF files and converts them into readable document format
from langchain_community.document_loaders import PyPDFLoader

# Splits large text into smaller chunks
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Stores embeddings and performs fast similarity search
from langchain_community.vectorstores import FAISS

# Converts text into numerical vectors
from langchain_community.embeddings import HuggingFaceEmbeddings

#  Connects to Groq LLM model
from langchain_groq import ChatGroq

# # LLM ko structured instruction dene ke liye template banata hai
from langchain_core.prompts import ChatPromptTemplate

# Converts LLM output into clean readable text
from langchain_core.output_parsers import StrOutputParser

# Loads environment variables from .env file
from dotenv import load_dotenv

# -------------------- ENV --------------------

# Load environment variables
load_dotenv()

# fetch  GROQ API key from env
api_key = os.getenv("GROQ_API_KEY")


# If API key not found, stop execution
if not api_key:
    st.error(" GROQ_API_KEY not found. Add it to your .env file.")
    st.stop()


# -------------------- UI --------------------

# Title of the app
st.title(" DDR Report Generator (AI Powered)")

# Small description
st.caption(" Preloaded inspection + Thermal Reports")


# -------------------- PDF PATHS --------------------

# define the path of Predefined PDF files
pdf_paths = [
    "inspection_report.pdf",
    "thermal_report.pdf"]


# -------------------- LOAD DOCUMENTS --------------------


# This list will store all documents
all_docs = []

# Loop through each PDF file
for path in pdf_paths:
    try:
           # Load PDF
        loader = PyPDFLoader(path)

        # Convert PDF into documents (pages)
        docs = loader.load()

        # Har document me source (kaunsi file se aaya) store kar rahe hain
        for doc in docs:
            doc.metadata["source"] = path

         # Add all documents into main list    
        all_docs.extend(docs)
    except Exception as e:

         # If file not found or error occurs
        st.error(f" Error loading {path}: {e}")

# Show success message
st.success(f" Loaded {len(all_docs)} pages")



# -------------------- CACHE VECTORSTORE --------------------

# Cache the vector store to avoid recomputation (Heavy computation ko bar-bar run hone se bachata hai (cache))
@st.cache_resource
def create_vectorstore(_docs: list):

      # Split documents into chunks
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    
     # Create chunks
    chunks = splitter.split_documents(_docs)

#   Convert text chunks into embeddings (vectors)
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
     # Store vectors in FAISS database(for fast search)
    return FAISS.from_documents(chunks, embeddings)



# -------------------- MAIN LOGIC --------------------


if all_docs:
      # Create vector store
    vectorstore = create_vectorstore(all_docs)

      # Retriever: finds relevant chunks based on user query
    retriever = vectorstore.as_retriever(search_kwargs={"k": 12})

    
    # -------------------- LLM --------------------
    
     # Initialize Groq LLM model
    llm = ChatGroq(
        groq_api_key=api_key,
        model_name="llama-3.1-8b-instant"
    )

    
    # -------------------- PROMPT --------------------
    
      # Defines how LLM should generate output
    prompt = ChatPromptTemplate.from_template("""
You are a senior building inspection analyst.

Your task is to generate a COMPLETE DDR (Detailed Diagnostic Report)
by analyzing BOTH inspection and thermal reports.

IMPORTANT INSTRUCTIONS:
- Include ALL issues from inspection report (even if not in thermal)
- Combine thermal + visual findings wherever possible
- Do NOT miss any area (bedroom, kitchen, balcony, etc.)
- Do NOT hallucinate

SEVERITY RULE:
- If both inspection + thermal confirm → HIGH
- If only one confirms → MEDIUM
- Minor issues → LOW

OUTPUT FORMAT:

1. Executive Summary
2. Key Findings (combined insights)
3. Detailed Issues:
   For each issue include:
   - Location
   - Issue Description
   - Severity
   - Evidence (Inspection + Thermal if available)
4. Structural Observations
5. Thermal Observations
6. Recommendations
7. Conclusion

Context:
{context}
""")

    
    # -------------------- FORMAT DOCS --------------------
    
    
    def format_docs(docs):
        # Combine all retrieved chunks into one string
        
        return "\n\n".join(
            f"[Source: {doc.metadata.get('source')}]\n{doc.page_content}"
            for doc in docs
        )

    
    # -------------------- PIPELINE --------------------
    
     # Define pipeline:
     # Retriever → Format → Prompt → LLM → Output Parser
    report_chain = (
        {"context": retriever | format_docs}       # relevant chunks extract + format
        | prompt                                    #  inject in prompt
        | llm                                        # LLM  generate answer
        | StrOutputParser()                            # clean output
    )

    
    # -------------------- BUTTON --------------------
    
    
    
    if st.button(" Generate DDR Report"):
        #  Show loading spinner
        with st.spinner("Generating professional report..."):
             # Invoke pipeline
            report = report_chain.invoke(
                "Generate a complete DDR report including all inspection and thermal findings"
            )

               # Display result
        st.markdown("# DDR Report")
        st.markdown(report)

#  Download button
        st.download_button(
            label=" Download Report",
            data=report,
            file_name="ddr_report.md",
            mime="text/markdown"
        )
