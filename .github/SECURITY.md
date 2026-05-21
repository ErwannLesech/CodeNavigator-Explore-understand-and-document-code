# Security Policy

CodeNavigator takes security seriously. This document outlines our security practices, supported versions, and how to responsibly report vulnerabilities.

---

## Supported Versions

We provide security updates for the following versions:

| Version | Supported          | End of Life       |
|---------|------------------|------------------|
| 1.x     | :white_check_mark: | TBD              |

**Security updates** will be released as patch versions (e.g., 1.0.1, 1.0.2) for the currently supported version. Users should upgrade to the latest available version to receive security fixes.

---

## Reporting a Vulnerability

### Responsible Disclosure

If you discover a security vulnerability in CodeNavigator, please **do not** open a public GitHub issue. Instead:

1. **Email the maintainers** at the contact email specified in the project repository
2. Include the following details:
   - Description of the vulnerability
   - Steps to reproduce (if applicable)
   - Potential impact
   - Suggested fix (if you have one)

### Timeline

- **Acknowledgment**: We will acknowledge receipt of your report within 48 hours
- **Assessment**: We aim to assess and triage the vulnerability within 5 business days
- **Fix & Release**: Critical vulnerabilities will be patched and released as soon as possible
- **Notification**: You will be informed before the public disclosure of any fix

### Accepted Vulnerabilities

Once a vulnerability is confirmed:
- A patch will be prepared and tested
- A security advisory will be released alongside the patch
- Credit will be given to the reporter (unless anonymity is requested)

### Declined Vulnerabilities

If we determine a report is not a valid security issue, we will explain our reasoning and keep communication open for further discussion.

---

## Security Best Practices

### For Users

1. **Keep dependencies updated**: Regularly update CodeNavigator and its dependencies
   ```bash
   pip install --upgrade -r requirements.txt
   ```

2. **Use environment variables for secrets**: Never commit API keys or credentials
   ```python
   from dotenv import load_dotenv
   api_key = os.getenv("MISTRAL_API_KEY")
   ```

3. **Run on trusted networks**: When using the FastAPI backend, restrict network access to trusted clients

### For Developers

1. **Dependency Management**:
   - All external dependencies are listed in `requirements.txt`
   - Pin major versions to prevent breaking changes
   - Regularly audit for known vulnerabilities using tools like `pip-audit` or `safety`

2. **Code Review**:
   - All pull requests require code review before merging
   - Security implications should be considered in reviews
   - Avoid hardcoding secrets—use `config.py` or environment variables

3. **Secrets & Credentials**:
   - Never commit `.env` files, API keys, or tokens
   - Use `.gitignore` to exclude sensitive files
   - Follow the configuration guide in `backend/config.py`

4. **Input Validation**:
   - All API inputs are validated using Pydantic models

5. **Logging**:
   - Use the `logging` module, never `print()` statements
   - Avoid logging sensitive information (API keys, tokens, passwords)
   - Configure appropriate log levels for production

---

## Vulnerability Scanning

We recommend users scan their environments:

```bash
# Check Python dependencies for known vulnerabilities
pip install safety
safety check

# Or use pip-audit
pip install pip-audit
pip-audit
```

---

## Contact

For security inquiries or to report vulnerabilities responsibly, please reach out to the project maintainers (lesech.erwann@gmail.com). Details are available in the [README.md](README.md).

---

## Community Standards

All contributors and community members are expected to abide by our [Code of Conduct](CODE_OF_CONDUCT.md). We are committed to fostering a respectful and inclusive environment where all members feel safe and valued.

---

## Changelog

- **[2026-05-07]**: Initial security policy document created
