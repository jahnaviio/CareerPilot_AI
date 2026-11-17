"""Skill taxonomy (canonical name, category, aliases) and evidence-preserving skill extraction."""
from __future__ import annotations

import re
from functools import lru_cache

# canonical: (category, [aliases])
TAXONOMY: dict[str, tuple[str, list[str]]] = {
    # languages
    "Python": ("language", ["python3"]), "Java": ("language", []), "C++": ("language", ["cpp"]),
    "C": ("language", []), "C#": ("language", ["csharp"]), "JavaScript": ("language", ["js", "ecmascript"]),
    "TypeScript": ("language", ["ts"]), "SQL": ("language", ["t-sql", "pl/sql"]), "R": ("language", []),
    "Go": ("language", ["golang"]), "Rust": ("language", []), "Kotlin": ("language", []), "Bash": ("language", ["shell scripting"]),
    "HTML": ("language", ["html5"]), "CSS": ("language", ["css3"]),
    # ML / AI
    "Machine Learning": ("ai_ml", ["ml"]), "Deep Learning": ("ai_ml", ["neural networks", "dl"]),
    "Natural Language Processing": ("ai_ml", ["nlp"]), "Computer Vision": ("ai_ml", ["cv", "image processing"]),
    "Generative AI": ("ai_ml", ["genai", "gen ai", "generative ai"]), "LLMs": ("ai_ml", ["llm", "large language models", "large language model"]),
    "Prompt Engineering": ("ai_ml", ["prompt design"]), "RAG": ("ai_ml", ["retrieval augmented generation", "retrieval-augmented generation"]),
    "AI Agents": ("ai_ml", ["agentic ai", "ai agent", "multi-agent", "agentic workflows", "agentic workflow"]),
    "Reinforcement Learning": ("ai_ml", []), "Transformers": ("ai_ml", ["bert", "gpt"]),
    "Fine-tuning": ("ai_ml", ["finetuning", "fine tuning", "lora", "peft"]), "Embeddings": ("ai_ml", ["sentence transformers", "sentence-transformers", "vector embeddings"]),
    "Vector Databases": ("ai_ml", ["chromadb", "chroma", "faiss", "pinecone", "weaviate", "qdrant", "vector database", "vector db"]),
    "Statistics": ("data", ["statistical analysis", "hypothesis testing"]), "Data Analysis": ("data", ["data analytics", "exploratory data analysis", "eda"]),
    "Data Visualization": ("data", ["data visualisation"]), "Feature Engineering": ("data", []), "Time Series": ("data", ["time-series"]),
    "A/B Testing": ("data", ["ab testing"]), "ETL": ("data", ["data pipelines", "data pipeline"]),
    # frameworks / libs
    "PyTorch": ("framework", ["torch"]), "TensorFlow": ("framework", ["tf"]), "Keras": ("framework", []),
    "Scikit-learn": ("framework", ["sklearn", "scikit learn"]), "Hugging Face": ("framework", ["huggingface", "hugging face transformers"]),
    "LangChain": ("framework", []), "LlamaIndex": ("framework", ["llama index", "llama-index"]), "OpenCV": ("framework", ["cv2"]),
    "Pandas": ("framework", []), "NumPy": ("framework", ["numpy"]), "Matplotlib": ("framework", []), "Seaborn": ("framework", []),
    "Streamlit": ("framework", []), "Gradio": ("framework", []), "FastAPI": ("framework", []), "Flask": ("framework", []),
    "Django": ("framework", []), "React": ("framework", ["reactjs", "react.js"]), "Next.js": ("framework", ["nextjs"]),
    "Node.js": ("framework", ["nodejs", "node"]), "Express": ("framework", ["express.js", "expressjs"]), "Spring Boot": ("framework", ["springboot"]),
    "Tailwind CSS": ("framework", ["tailwind"]), "Pydantic": ("framework", []), "SQLAlchemy": ("framework", []),
    "Spark": ("framework", ["pyspark", "apache spark"]), "Airflow": ("framework", ["apache airflow"]),
    # tools / platforms
    "Git": ("tool", []), "GitHub": ("tool", []), "Docker": ("tool", []), "Kubernetes": ("tool", ["k8s"]),
    "Linux": ("tool", []), "AWS": ("cloud", ["amazon web services"]), "Azure": ("cloud", ["microsoft azure"]),
    "GCP": ("cloud", ["google cloud", "google cloud platform"]), "Vercel": ("tool", []), "Render": ("tool", []),
    "Supabase": ("tool", []), "Firebase": ("tool", []), "Ollama": ("tool", []), "Postman": ("tool", []),
    "Power BI": ("tool", ["powerbi"]), "Tableau": ("tool", []), "Excel": ("tool", ["microsoft excel", "ms excel"]),
    "Jupyter": ("tool", ["jupyter notebook", "jupyter notebooks"]), "CI/CD": ("tool", ["github actions", "jenkins"]),
    "MLflow": ("tool", []), "Salesforce": ("tool", ["apex", "lwc"]),
    # databases & backend
    "PostgreSQL": ("database", ["postgres"]), "MySQL": ("database", []), "MongoDB": ("database", []),
    "SQLite": ("database", []), "Redis": ("database", []), "REST APIs": ("backend", ["rest api", "restful", "restful api", "restful apis"]),
    "GraphQL": ("backend", []), "Microservices": ("backend", []), "Authentication": ("backend", ["jwt", "oauth"]),
    # CS fundamentals
    "Data Structures and Algorithms": ("fundamentals", ["dsa", "data structures", "algorithms"]),
    "Object-Oriented Programming": ("fundamentals", ["oop", "oops"]), "Operating Systems": ("fundamentals", []),
    "DBMS": ("fundamentals", ["database management systems"]), "Computer Networks": ("fundamentals", []),
    "Software Testing": ("fundamentals", ["unit testing", "pytest", "test automation"]), "System Design": ("fundamentals", []),
    "Agile": ("fundamentals", ["scrum"]),
}


@lru_cache(maxsize=1)
def _patterns() -> list[tuple[str, str, re.Pattern]]:
    out = []
    for canon, (cat, aliases) in TAXONOMY.items():
        terms = {canon.lower(), *[a.lower() for a in aliases]}
        alt = "|".join(sorted((re.escape(t) for t in terms), key=len, reverse=True))
        # custom boundaries so C++, C#, Node.js, CI/CD work; a bare letter-only alias must not match inside a word
        guard = r"(?<!sentence )(?<!sentence-)" if canon == "Transformers" else ""
        out.append((canon, cat, re.compile(rf"(?<![A-Za-z0-9+#.]){guard}{'(?:' + alt + ')'}(?![A-Za-z0-9+#])", re.I)))
    return out


def category_of(skill: str) -> str:
    return TAXONOMY.get(skill, ("other", []))[0]


def find_skills_in_text(text: str) -> list[str]:
    """Canonical skills mentioned anywhere in free text (resume or job description)."""
    found = []
    for canon, _cat, pat in _patterns():
        # single-letter languages are ambiguous in prose: require nearby programming context
        if canon in ("R", "C", "Go") and not _ambiguous_ok(canon, text):
            continue
        if pat.search(text):
            found.append(canon)
    return found


_CTX = re.compile(r"(programming|language|python|java|sql|skills?|developer|engineer|proficien|experience with|coding)", re.I)


def _ambiguous_ok(canon: str, text: str) -> bool:
    pat = {"R": r"(?<![A-Za-z0-9+#.])R(?![A-Za-z0-9+#])", "C": r"(?<![A-Za-z0-9+#.])C(?![A-Za-z0-9+#])",
           "Go": r"(?<![A-Za-z0-9+#.])(?:Go|Golang)(?![A-Za-z0-9+#])"}[canon]
    for m in re.finditer(pat, text):  # case-sensitive on purpose
        window = text[max(0, m.start() - 60): m.end() + 60]
        if _CTX.search(window) or re.search(r"[,/|•]\s*" + re.escape(m.group(0)) + r"\s*[,/|•\n]", window):
            return True
    return False


def skills_with_evidence(lines_by_section: list[tuple[str, str]]) -> dict[str, dict]:
    """lines_by_section: [(section_name, line)]. Returns {skill: {sections:set, evidence:[line,...]}}."""
    result: dict[str, dict] = {}
    for section, line in lines_by_section:
        for skill in find_skills_in_text(line):
            d = result.setdefault(skill, {"sections": set(), "evidence": []})
            d["sections"].add(section)
            if len(d["evidence"]) < 3 and line.strip() not in d["evidence"]:
                d["evidence"].append(line.strip()[:240])
    return result
