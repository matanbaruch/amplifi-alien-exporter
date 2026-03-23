# Contributing to AmpliFi Alien Exporter

Thank you for your interest in contributing! Here's how to get started.

## Getting Started

1. **Fork** the repository on GitHub
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/amplifi-alien-exporter.git
   cd amplifi-alien-exporter
   ```
3. **Create a branch** for your change:
   ```bash
   git checkout -b feature/my-improvement
   ```

## Development

No external dependencies are required — the exporter uses only the Python standard library.

### Running Tests

```bash
# With unittest (built-in)
python -m unittest discover tests/ -v

# With pytest (optional)
pip install pytest
python -m pytest tests/ -v
```

### Code Style

- Follow [PEP 8](https://pep8.org/)
- Use type hints where practical
- Keep the zero-dependency philosophy: **stdlib only**

## Pull Requests

1. Ensure all tests pass
2. Add tests for any new functionality
3. Update `README.md` if you add/change environment variables or metrics
4. Keep commits clean and descriptive
5. Open a PR against the `main` branch with a clear description

## Reporting Issues

- Use the [GitHub Issues](https://github.com/matanbaruch/amplifi-alien-exporter/issues) tracker
- Include your AmpliFi firmware version, Python version, and relevant log output

## Security Issues

Please **do not** open a public issue for security vulnerabilities. See [SECURITY.md](SECURITY.md) for the responsible disclosure process.

## Code of Conduct

Be respectful, constructive, and inclusive. We're all here to make things better.
