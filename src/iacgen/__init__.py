"""iacgen: generate GitHub Actions CI/CD pipelines and Terraform modules
from a short project description.
"""

__version__ = "0.1.0"

from .models import ProjectSpec, ProjectSpecError

__all__ = ["ProjectSpec", "ProjectSpecError", "__version__"]
