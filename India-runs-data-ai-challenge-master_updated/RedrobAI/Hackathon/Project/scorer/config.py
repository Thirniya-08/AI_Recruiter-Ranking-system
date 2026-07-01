"""
Configuration — all weights, thresholds, keyword lists, and scoring parameters.

Centralised here so tuning is easy and the scoring modules stay clean.
"""

from datetime import date

# ---------------------------------------------------------------------------
# Reference date for recency calculations
# ---------------------------------------------------------------------------
TODAY = date(2026, 6, 18)

# ---------------------------------------------------------------------------
# Component weights  (must sum to ~1.0 before behavioral modifier)
# ---------------------------------------------------------------------------
W_TITLE_CAREER = 0.35
W_SKILLS       = 0.20
W_EXPERIENCE   = 0.20
W_LOCATION     = 0.10
W_EDUCATION    = 0.05
W_BEHAVIORAL   = 0.10  # added as a separate additive component

# ---------------------------------------------------------------------------
# Title tiers — mapped to base scores
# ---------------------------------------------------------------------------
TIER_1_TITLES = [
    "ai engineer", "ml engineer", "machine learning engineer",
    "senior ai engineer", "senior ml engineer",
    "senior machine learning engineer", "applied scientist",
    "nlp engineer", "search engineer", "ranking engineer",
    "recommendation engineer", "deep learning engineer",
    "applied ml engineer", "staff ai engineer", "staff ml engineer",
    "lead ai engineer", "lead ml engineer", "principal ai engineer",
    "ai/ml engineer", "ml/ai engineer",
]

TIER_2_TITLES = [
    "data scientist", "senior data scientist", "lead data scientist",
    "software engineer", "senior software engineer",
    "backend engineer", "senior backend engineer",
    "full stack engineer", "platform engineer",
    "research engineer", "research scientist",
    "junior ai engineer", "junior ml engineer",
    "junior machine learning engineer",
]

TIER_3_TITLES = [
    "data engineer", "senior data engineer", "data analyst",
    "senior data analyst", "devops engineer", "sre",
    "cloud engineer", "solutions architect",
    "technical lead", "engineering manager",
]

IRRELEVANT_TITLES = [
    "hr manager", "marketing manager", "accountant",
    "graphic designer", "content writer", "sales executive",
    "mechanical engineer", "civil engineer", "customer support",
    "operations manager", "project manager", "product manager",
    "business analyst", "financial analyst", "teacher",
    "recruiter", "admin", "executive assistant",
    "quality analyst", "qa engineer",  # QA without ML context
]

TITLE_TIER_SCORES = {
    1: 1.0,
    2: 0.65,
    3: 0.35,
    "irrelevant": 0.05,
    "unknown": 0.20,
}

# ---------------------------------------------------------------------------
# Career-description keywords (searched in role descriptions)
# ---------------------------------------------------------------------------
CAREER_KW_HIGH = [
    # Core ranking / retrieval / search
    "ranking", "re-ranking", "reranking", "retrieval", "information retrieval",
    "search engine", "search relevance", "learning to rank", "learning-to-rank",
    "candidate matching", "talent matching", "job matching",
    "recommendation system", "recommender system", "collaborative filtering",
    "content-based filtering", "hybrid search",
    # Embeddings & vectors
    "embedding", "embeddings", "vector search", "vector database",
    "sentence-transformers", "sentence transformer", "bge", "e5 model",
    "faiss", "pinecone", "weaviate", "qdrant", "milvus",
    "elasticsearch", "opensearch", "solr", "lucene",
    "semantic search", "dense retrieval", "sparse retrieval",
    "approximate nearest neighbor", "ann", "hnsw",
    # NLP & transformers
    "nlp", "natural language processing", "bert", "transformer",
    "hugging face", "huggingface", "tokenizer", "fine-tuning",
    "fine-tune", "finetuning", "finetune",
    "text classification", "named entity recognition", "ner",
    "sentiment analysis", "text generation",
    # LLMs
    "llm", "large language model", "gpt", "rag",
    "retrieval augmented generation", "prompt engineering",
    "lora", "qlora", "peft", "instruction tuning",
    # Evaluation
    "ndcg", "mrr", "map", "precision@k", "recall@k",
    "a/b test", "a/b testing", "offline evaluation",
    "online evaluation", "evaluation framework",
]

CAREER_KW_MED = [
    # General ML
    "machine learning", "deep learning", "neural network",
    "pytorch", "tensorflow", "keras", "scikit-learn", "sklearn",
    "xgboost", "lightgbm", "catboost", "gradient boosting",
    "random forest", "logistic regression",
    "model training", "model serving", "model deployment",
    "mlops", "ml pipeline", "feature engineering", "feature store",
    "experiment tracking", "weights and biases", "wandb", "mlflow",
    # Data / infra related to ML
    "data pipeline", "etl", "airflow", "spark", "pyspark",
    "data warehouse", "bigquery", "redshift", "snowflake",
    # Production systems
    "production ml", "production model", "model monitoring",
    "inference", "batch inference", "real-time inference",
    "microservice", "api", "rest api", "grpc",
    "docker", "kubernetes", "k8s",
    "ci/cd", "github actions",
    # Python ecosystem
    "python", "pandas", "numpy", "scipy",
    "jupyter", "notebook",
]

# ---------------------------------------------------------------------------
# Skills — must-have vs nice-to-have (for the JD)
# ---------------------------------------------------------------------------
MUST_HAVE_SKILL_GROUPS = {
    "embeddings_retrieval": [
        "embeddings", "sentence-transformers", "sentence transformers",
        "bge", "e5", "openai embeddings", "word2vec", "glove",
        "dense retrieval", "semantic search", "vector search",
        "embedding", "text embeddings",
    ],
    "vector_db_search": [
        "pinecone", "weaviate", "qdrant", "milvus", "faiss",
        "elasticsearch", "opensearch", "solr", "lucene",
        "vector database", "hybrid search", "annoy", "hnsw",
    ],
    "python": [
        "python",
    ],
    "eval_ranking": [
        "ndcg", "mrr", "map", "evaluation", "a/b testing",
        "ranking evaluation", "precision", "recall",
        "offline evaluation", "online evaluation",
    ],
}

NICE_TO_HAVE_SKILL_GROUPS = {
    "llm_finetuning": [
        "lora", "qlora", "peft", "fine-tuning llms",
        "fine-tuning", "finetuning", "instruction tuning",
        "llm", "large language model",
    ],
    "learning_to_rank": [
        "xgboost", "lightgbm", "catboost",
        "learning to rank", "gradient boosting",
        "ranking model",
    ],
    "nlp_core": [
        "nlp", "natural language processing",
        "ner", "named entity recognition",
        "text classification", "tokenization", "tokenizer",
        "bert", "transformer", "transformers",
        "huggingface", "hugging face",
    ],
    "deep_learning": [
        "pytorch", "tensorflow", "keras",
        "deep learning", "neural network",
        "cnn", "rnn", "lstm", "attention",
    ],
    "mlops_infra": [
        "mlops", "docker", "kubernetes", "k8s",
        "mlflow", "wandb", "weights and biases",
        "model serving", "model deployment",
        "airflow", "kubeflow",
    ],
}

# ---------------------------------------------------------------------------
# Consulting / services companies (entire-career = penalty)
# ---------------------------------------------------------------------------
CONSULTING_COMPANIES = [
    "tcs", "infosys", "wipro", "accenture", "cognizant",
    "capgemini", "hcl", "tech mahindra", "mindtree", "mphasis",
    "hexaware", "l&t infotech", "lti", "ltimindtree",
    "cyient", "persistent systems", "zensar",
    "deloitte", "pwc", "ey", "kpmg",  # big-4 consulting
]

# ---------------------------------------------------------------------------
# Location config
# ---------------------------------------------------------------------------
PREFERRED_CITIES = [
    "pune", "noida",
]

ACCEPTABLE_CITIES = [
    "hyderabad", "mumbai", "delhi", "new delhi", "gurgaon", "gurugram",
    "delhi ncr", "ncr", "bangalore", "bengaluru", "chennai", "kolkata",
]

INDIA_COUNTRY_NAMES = ["india"]

# ---------------------------------------------------------------------------
# Education — relevant fields and tier bonuses
# ---------------------------------------------------------------------------
CS_FIELDS = [
    "computer science", "computer engineering",
    "machine learning", "artificial intelligence",
    "data science", "information technology",
    "statistics", "mathematics", "math",
    "electronics", "electrical engineering",
    "electronics and communication",
    "software engineering",
]

TIER_BONUS = {
    "tier_1": 0.30,
    "tier_2": 0.20,
    "tier_3": 0.10,
    "tier_4": 0.00,
    "unknown": 0.05,
}

DEGREE_BONUS = {
    "ph.d": 0.15, "phd": 0.15,
    "m.tech": 0.15, "mtech": 0.15,
    "m.e.": 0.12, "me": 0.12,
    "m.sc": 0.10, "msc": 0.10, "m.s.": 0.10,
    "mba": 0.05,
    "b.tech": 0.08, "btech": 0.08,
    "b.e.": 0.08, "be": 0.08,
    "b.sc": 0.05, "bsc": 0.05, "b.s.": 0.05,
}

# ---------------------------------------------------------------------------
# Behavioral signal thresholds
# ---------------------------------------------------------------------------
BEHAVIORAL = {
    "active_days_excellent": 7,
    "active_days_good": 30,
    "active_days_ok": 90,
    "active_days_stale": 180,
    "response_rate_high": 0.70,
    "response_rate_ok": 0.40,
    "response_rate_low": 0.20,
    "response_time_fast_hrs": 24,
    "response_time_ok_hrs": 72,
    "github_strong": 50,
    "github_moderate": 20,
    "saved_by_high": 10,
    "saved_by_moderate": 5,
    "interview_good": 0.80,
    "interview_bad": 0.50,
    "completeness_good": 80,
}
