"""Learning resources and project ideas. Links are OFFICIAL documentation/tutorial landing pages chosen for stability;
they are not fetched or verified from the server. Skills without an entry get a generic project idea and no link."""
RESOURCES: dict[str, list[tuple[str, str]]] = {
    "Python": [("The Python Tutorial (official)", "https://docs.python.org/3/tutorial/")],
    "SQL": [("SQLBolt interactive lessons", "https://sqlbolt.com/")],
    "Git": [("Pro Git book", "https://git-scm.com/book/en/v2")],
    "Machine Learning": [("scikit-learn User Guide", "https://scikit-learn.org/stable/user_guide.html")],
    "Scikit-learn": [("scikit-learn User Guide", "https://scikit-learn.org/stable/user_guide.html")],
    "Deep Learning": [("PyTorch Tutorials", "https://pytorch.org/tutorials/")],
    "PyTorch": [("PyTorch Tutorials", "https://pytorch.org/tutorials/")],
    "TensorFlow": [("TensorFlow Tutorials", "https://www.tensorflow.org/tutorials")],
    "Natural Language Processing": [("Hugging Face LLM/NLP Course", "https://huggingface.co/learn")],
    "Transformers": [("Hugging Face Transformers docs", "https://huggingface.co/docs/transformers")],
    "Hugging Face": [("Hugging Face Learn", "https://huggingface.co/learn")],
    "LLMs": [("Hugging Face Learn", "https://huggingface.co/learn")],
    "RAG": [("LangChain docs", "https://python.langchain.com/docs/")],
    "LangChain": [("LangChain docs", "https://python.langchain.com/docs/")],
    "Vector Databases": [("Chroma docs", "https://docs.trychroma.com/")],
    "Embeddings": [("Sentence Transformers docs", "https://www.sbert.net/")],
    "FastAPI": [("FastAPI Tutorial", "https://fastapi.tiangolo.com/tutorial/")],
    "Docker": [("Docker Get Started", "https://docs.docker.com/get-started/")],
    "Pandas": [("pandas User Guide", "https://pandas.pydata.org/docs/user_guide/index.html")],
    "NumPy": [("NumPy quickstart", "https://numpy.org/doc/stable/user/quickstart.html")],
    "React": [("React - Learn", "https://react.dev/learn")],
    "TypeScript": [("TypeScript Handbook", "https://www.typescriptlang.org/docs/handbook/intro.html")],
    "Next.js": [("Next.js Learn", "https://nextjs.org/learn")],
    "PostgreSQL": [("PostgreSQL Tutorial (official docs)", "https://www.postgresql.org/docs/current/tutorial.html")],
    "Statistics": [("Khan Academy Statistics", "https://www.khanacademy.org/math/statistics-probability")],
    "Flask": [("Flask Quickstart", "https://flask.palletsprojects.com/en/stable/quickstart/")],
    "Django": [("Django Tutorial", "https://docs.djangoproject.com/en/stable/intro/tutorial01/")],
    "AWS": [("AWS Skill Builder", "https://skillbuilder.aws/")],
    "Kubernetes": [("Kubernetes Basics", "https://kubernetes.io/docs/tutorials/kubernetes-basics/")],
    "Power BI": [("Power BI guided learning", "https://learn.microsoft.com/power-bi/learning-catalog/")],
    "Tableau": [("Tableau Training", "https://www.tableau.com/learn/training")],
    "MLflow": [("MLflow docs", "https://mlflow.org/docs/latest/")],
    "Data Structures and Algorithms": [("CS50 (Harvard, free)", "https://cs50.harvard.edu/x/")],
    "Software Testing": [("pytest documentation", "https://docs.pytest.org/")],
    "REST APIs": [("FastAPI Tutorial", "https://fastapi.tiangolo.com/tutorial/")],
    "Prompt Engineering": [("Hugging Face Learn", "https://huggingface.co/learn")],
}

PROJECTS: dict[str, str] = {
    "RAG": "Build a question-answering app over your own notes or PDFs that shows which passages each answer came from, and measure retrieval quality on 20 questions you wrote.",
    "LLMs": "Build a small app that calls an LLM through an API, validates its JSON output, and handles failures gracefully.",
    "Prompt Engineering": "Write 3 prompt variants for one task, test them on 15 inputs, and record which works best and why.",
    "Embeddings": "Build semantic search over a set of documents and compare it with keyword search on 10 test queries.",
    "Vector Databases": "Index a document collection in a vector database and add metadata filtering.",
    "FastAPI": "Wrap one of your models or scripts in a FastAPI service with input validation and a test suite.",
    "Docker": "Containerise one of your existing projects and write a README section on how to run it.",
    "Machine Learning": "Train and compare 3 scikit-learn models on a public dataset; report precision/recall on a held-out split.",
    "Deep Learning": "Train a small neural network in PyTorch on a public dataset and plot training vs validation loss.",
    "Natural Language Processing": "Build a text classifier on a public dataset and report precision, recall and F1 on a held-out set.",
    "SQL": "Answer 15 business questions on a public dataset using joins, aggregation and window functions.",
    "Statistics": "Run and interpret an A/B test analysis on a public dataset, including confidence intervals.",
    "Git": "Use branches and pull requests on a personal project and write clear commit messages.",
    "REST APIs": "Design and document a small REST API with authentication and tests.",
    "Data Visualization": "Build a dashboard from a public dataset that answers 3 specific questions.",
    "Software Testing": "Add unit and integration tests to an existing project and run them in CI.",
    "React": "Build a small responsive front-end that consumes a public API.",
    "AI Agents": "Build a workflow where an LLM calls 2-3 tools, with validation of each tool result and a log of every step.",
}


def resources_for(skill: str) -> list[dict]:
    return [{"title": t, "url": u} for t, u in RESOURCES.get(skill, [])]


def project_for(skill: str) -> str:
    return PROJECTS.get(skill, f"Build a small project that uses {skill}, publish it on GitHub, and describe what you built and the result on your resume.")
