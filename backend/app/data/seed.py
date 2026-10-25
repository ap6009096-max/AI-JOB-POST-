DEMO_COMPANY_ID = "company-demo"
DEMO_JOB_ID = "job-demo-fullstack"
DEMO_OWNER_ID = "00000000-0000-0000-0000-000000000001"

DEMO_COMPANY = {
    "id": DEMO_COMPANY_ID,
    "name": "Northwind Labs",
    "owner_id": DEMO_OWNER_ID,
}

DEMO_JOB = {
    "id": DEMO_JOB_ID,
    "company_id": DEMO_COMPANY_ID,
    "title": "Senior Full Stack Engineer",
    "description": (
        "Build hiring workflows in TypeScript and Python. Own React dashboards, "
        "FastAPI services, and PostgreSQL schemas for an AI recruitment platform."
    ),
    "requirements": {
        "skills": ["Python", "TypeScript", "React", "FastAPI", "PostgreSQL"],
        "experience_years": 5,
        "location": "Bengaluru",
        "keywords": ["full stack", "hiring", "api", "dashboard"],
    },
}


def _portal(
    cid: str,
    name: str,
    skills: list[str],
    years: float,
    location: str,
    summary: str,
    title: str,
) -> dict:
    return {
        "id": cid,
        "profile": {
            "name": name,
            "title": title,
            "skills": skills,
            "experience_years": years,
            "location": location,
            "resume_summary": summary,
        },
    }


def _external(
    cid: str,
    name: str,
    source: str,
    url: str,
    skills: list[str],
    years: float,
    location: str,
    summary: str,
    title: str,
) -> dict:
    return {
        "id": cid,
        "profile": {
            "name": name,
            "title": title,
            "source": source,
            "url": url,
            "skills": skills,
            "experience_years": years,
            "location": location,
            "resume_summary": summary,
        },
    }


PORTAL_CANDIDATES = [
    _portal("pc-01", "Asha Menon", ["Python", "TypeScript", "React", "FastAPI", "PostgreSQL"], 7, "Bengaluru", "Led FastAPI and Next.js hiring tools for 6 years.", "Staff Full Stack Engineer"),
    _portal("pc-02", "Rohit Iyer", ["Python", "FastAPI", "PostgreSQL", "Docker"], 6, "Bengaluru", "Backend-heavy full stack with PostgreSQL modeling.", "Senior Backend Engineer"),
    _portal("pc-03", "Neha Kapoor", ["TypeScript", "React", "PostgreSQL"], 5, "Bengaluru", "Dashboard specialist with hiring-ops UI work.", "Senior Frontend Engineer"),
    _portal("pc-04", "Vikram Shah", ["Python", "TypeScript", "React", "FastAPI"], 8, "Hyderabad", "Full stack platform engineer, remote-friendly.", "Principal Engineer"),
    _portal("pc-05", "Meera Nair", ["Python", "LangChain", "PostgreSQL"], 4, "Bengaluru", "Applied NLP to resume parsing prototypes.", "ML Engineer"),
    _portal("pc-06", "Arjun Patel", ["Java", "Spring", "PostgreSQL"], 9, "Pune", "Enterprise Java services, limited TypeScript.", "Senior Java Engineer"),
    _portal("pc-07", "Sara Khan", ["TypeScript", "React", "Node.js"], 3, "Bengaluru", "Product frontend for recruiting CRMs.", "Frontend Engineer"),
    _portal("pc-08", "Dev Sharma", ["Python", "FastAPI", "React", "TypeScript", "PostgreSQL"], 5, "Bengaluru", "Shipped end-to-end job boards.", "Full Stack Engineer"),
    _portal("pc-09", "Lina Bose", ["Go", "Kubernetes", "PostgreSQL"], 6, "Bengaluru", "Infrastructure and APIs, no React.", "Platform Engineer"),
    _portal("pc-10", "Farhan Ali", ["Python", "Django", "React"], 2, "Chennai", "Early-career full stack, Django not FastAPI.", "Software Engineer"),
    _portal("pc-11", "Priya Das", ["TypeScript", "React", "FastAPI", "PostgreSQL"], 6, "Bengaluru", "Hiring analytics dashboards and APIs.", "Senior Full Stack Engineer"),
    _portal("pc-12", "Owen Blake", ["Python", "TypeScript", "PostgreSQL"], 10, "London", "Staff engineer, relocation possible.", "Staff Engineer"),
    _portal("pc-13", "Kavya Rao", ["Figma", "User Research"], 7, "Bengaluru", "Product designer, not an engineer.", "Product Designer"),
    _portal("pc-14", "Nikhil Jain", ["Python", "FastAPI", "pgvector", "PostgreSQL"], 5, "Bengaluru", "Search and ranking services.", "Search Engineer"),
    _portal("pc-15", "Elena Rossi", ["TypeScript", "React", "GraphQL"], 4, "Milan", "Frontend contractor, no Python.", "React Engineer"),
    _portal("pc-16", "Harish Pillai", ["Python", "TypeScript", "React", "PostgreSQL"], 6, "Bengaluru", "Full stack on internal ATS.", "Senior Software Engineer"),
    _portal("pc-17", "Mia Thompson", ["Python", "FastAPI", "TypeScript"], 5, "Bengaluru", "API and dashboard pairing.", "Full Stack Engineer"),
    _portal("pc-18", "Aditya Kulkarni", ["C++", "Python"], 8, "Bengaluru", "Systems plus some Python scripting.", "Systems Engineer"),
    _portal("pc-19", "Grace Park", ["TypeScript", "React", "FastAPI", "PostgreSQL"], 4, "Bengaluru", "Hiring-ops UI and Python APIs.", "Software Engineer"),
    _portal("pc-20", "Yusuf Rahman", ["Python", "TypeScript", "React", "FastAPI", "PostgreSQL"], 9, "Bengaluru", "Built a candidate ranking prototype.", "Staff Full Stack Engineer"),
]

EXTERNAL_CANDIDATES = [
    _external("ec-01", "Maya Chen", "LinkedIn", "https://linkedin.com/in/maya-chen", ["Python", "TypeScript", "React", "FastAPI", "PostgreSQL"], 8, "Bengaluru", "Open to full stack roles in hiring tech.", "Senior Full Stack Engineer"),
    _external("ec-02", "James Okonkwo", "GitHub", "https://github.com/jokonkwo", ["Python", "FastAPI", "PostgreSQL"], 6, "Lagos", "API-first engineer, public FastAPI repos.", "Backend Engineer"),
    _external("ec-03", "Sofia Alvarez", "LinkedIn", "https://linkedin.com/in/sofia-alvarez", ["TypeScript", "React", "PostgreSQL"], 5, "Bengaluru", "Built talent-marketplace UIs.", "Frontend Engineer"),
    _external("ec-04", "Hiro Tanaka", "Indeed", "https://indeed.com/hiro-tanaka", ["Java", "Kotlin", "PostgreSQL"], 11, "Tokyo", "Mobile and JVM services.", "Android Engineer"),
    _external("ec-05", "Amelia Wright", "Wellfound", "https://wellfound.com/amelia-wright", ["Python", "TypeScript", "React", "PostgreSQL"], 7, "Bengaluru", "Startup full stack, hiring tools.", "Full Stack Engineer"),
    _external("ec-06", "Rahul Verma", "GitHub", "https://github.com/rahulverma", ["Python", "LangGraph", "FastAPI"], 4, "Delhi", "AI agent prototypes, some React.", "AI Engineer"),
    _external("ec-07", "Chloe Martin", "LinkedIn", "https://linkedin.com/in/chloe-martin", ["TypeScript", "React", "FastAPI"], 6, "Paris", "Willing to relocate to Bengaluru.", "Senior Frontend Engineer"),
    _external("ec-08", "Sanjay Gupta", "Naukri", "https://naukri.com/sanjay-gupta", ["Python", "FastAPI", "React", "TypeScript", "PostgreSQL"], 9, "Bengaluru", "Led a 12-person platform team.", "Engineering Manager"),
    _external("ec-09", "Nora Berg", "LinkedIn", "https://linkedin.com/in/nora-berg", ["Python", "Django", "PostgreSQL"], 5, "Stockholm", "Backend web, no TypeScript.", "Backend Engineer"),
    _external("ec-10", "Imran Qureshi", "GitHub", "https://github.com/imranq", ["Go", "PostgreSQL", "gRPC"], 8, "Bengaluru", "Systems engineer, limited UI.", "Systems Engineer"),
    _external("ec-11", "Hannah Lee", "Wellfound", "https://wellfound.com/hannah-lee", ["TypeScript", "React", "Node.js", "PostgreSQL"], 5, "Singapore", "Full stack JS, learning Python.", "Full Stack Engineer"),
    _external("ec-12", "Diego Santos", "LinkedIn", "https://linkedin.com/in/diego-santos", ["Python", "FastAPI", "pgvector", "PostgreSQL"], 6, "Bengaluru", "Similarity search and ranking.", "ML Platform Engineer"),
    _external("ec-13", "Ananya Iyer", "Naukri", "https://naukri.com/ananya-iyer", ["Recruiter", "ATS"], 10, "Bengaluru", "In-house recruiter, not technical.", "Technical Recruiter"),
    _external("ec-14", "Ben Carter", "GitHub", "https://github.com/bencarter", ["Python", "TypeScript", "React", "FastAPI"], 3, "Austin", "Junior-mid full stack, remote.", "Software Engineer"),
    _external("ec-15", "Zara Ahmed", "LinkedIn", "https://linkedin.com/in/zara-ahmed", ["Python", "TypeScript", "React", "FastAPI", "PostgreSQL"], 12, "Bengaluru", "Head of engineering, still hands-on.", "VP Engineering"),
    _external("ec-16", "Tom Becker", "GitHub", "https://github.com/tombecker", ["Python", "FastAPI", "React"], 5, "Berlin", "Open-source FastAPI starter kits.", "Full Stack Engineer"),
    _external("ec-17", "Ishita Malhotra", "LinkedIn", "https://linkedin.com/in/ishita-malhotra", ["TypeScript", "React", "PostgreSQL", "Python"], 6, "Bengaluru", "Marketplace search UI.", "Senior Full Stack Engineer"),
    _external("ec-18", "Luis Romero", "Wellfound", "https://wellfound.com/luis-romero", ["Python", "pandas"], 4, "Mexico City", "Data engineer, not product UI.", "Data Engineer"),
    _external("ec-19", "Nadia Hassan", "Naukri", "https://naukri.com/nadia-hassan", ["Python", "TypeScript", "FastAPI", "PostgreSQL"], 7, "Bengaluru", "API platform for HR tools.", "Backend Engineer"),
    _external("ec-20", "Peter Novak", "LinkedIn", "https://linkedin.com/in/peter-novak", ["TypeScript", "React"], 2, "Prague", "Junior frontend only.", "Junior Frontend Engineer"),
]
