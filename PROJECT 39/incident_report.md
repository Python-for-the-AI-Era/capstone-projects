# CI/CD Resolution: Scrapy Dependency Conflict

## 1. Problem: The "Ghost" Dependency
The error `ModuleNotFoundError: No module named _lxml_html_clean` was caused by a breaking change in the `lxml` library (v5.2.0). Newer versions removed the `html.clean` module into a separate package. Our local environments had the old version cached, while Docker pulled the new, broken version.

## 2. Immediate Fix
- **Explicit Pinning:** Forced `lxml==4.9.4` and added `lxml-html-clean` to the `pyproject.toml`.
- **System Headers:** Added `libxml2-dev` to the Dockerfile to ensure C extensions compile correctly on Linux.

## 3. Future Prevention
- **Scrapy Check:** We now run `scrapy check` in the CI pipeline. If an import is missing, the build fails in 30 seconds rather than waiting for a full deployment crash.
- **Lock Files:** We are moving to **uv** or **Poetry** to generate `uv.lock` files, ensuring byte-for-byte environment parity.

## 4. Platform Metrics
- **Build Success (amd64):** 100%
- **Build Success (arm64):** 100%