import setuptools # type: ignore

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()
    
    
__version__ = "0.0.1"
    
    
REPO_NAME = "HITL-Incident-Engine"
AUTHOR_USER_NAME = "Koushik25022005"
AUTHOR_EMAIL = "sripathikoushik244@gmail.com"

setuptools.setup(
    name=REPO_NAME,
    version=__version__,
    author=AUTHOR_USER_NAME,
    author_email=AUTHOR_EMAIL,
    description="A Human-in-the-loop incident engine that leverages LLMs to generate incident reports and summaries.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url=f"https://github.com/{AUTHOR_USER_NAME}/{REPO_NAME}",
    packages=setuptools.find_packages(),
)