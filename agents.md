# AGENTS.md - Development Guidelines for SimplySignage

## Build/Lint/Test Commands

### Python Environment & Dependencies
- **Package Management**: Use `uv` for all Python operations
- **Install dependencies**: `uv sync`
- **Add package**: `uv add <package>`
- **Run Python script**: `uv run <script.py>`
- **Django commands**: `uv run python manage.py <command>`

### Django Management Commands
- **Run development server**: `uv run python manage.py runserver 8000`
- **Run migrations**: `uv run python manage.py migrate`
- **Create migration**: `uv run python manage.py makemigrations`
- **Collect static files**: `uv run python manage.py collectstatic --no-input`

### Testing
- **Run all tests**: `uv run python manage.py test`
- **Run specific test file**: `uv run python manage.py test signage.tests_asset_tracking`
- **Run single test method**: `uv run python manage.py test signage.tests_asset_tracking.AssetTrackingTestCase.test_calculate_asset_display_stats`
- **Run tests with coverage**: `uv run python manage.py test --verbosity=2`



## Code Style Guidelines

### Python Conventions
- **Imports**: Standard library → Django → Third-party → Local modules
- **Line length**: Keep lines under 100 characters when possible
- **Docstrings**: Use triple quotes for function/class documentation
- **Naming**: snake_case for variables/functions, PascalCase for classes
- **Error handling**: Use try/except blocks with specific exceptions

### Django-Specific Patterns
- **Models**: Inherit from BaseModel for uuid/slug/deleted fields
- **Views**: Use @login_required and custom decorators for access control
- **URLs**: Use reverse() for URL generation instead of hardcoded paths
- **Templates**: Use descriptive context variable names
- **Forms**: Validate data thoroughly with custom validators

### Logging
- **Logger**: Use `loguru` logger throughout the codebase
- **Log levels**: DEBUG for development, INFO for production events, ERROR for exceptions
- **Context**: Include relevant IDs (user, device, asset) in log messages

### Database
- **Queries**: Use select_related/prefetch_related for optimization
- **Soft deletes**: Use `deleted=False` in queries (BaseModel pattern)
- **Validation**: Implement model validators for business logic
- **Migrations**: Always test migrations before deploying

### JavaScript/CSS
- **Tailwind**: Use utility-first approach with custom CSS variables
- **HTMX**: Leverage for dynamic interactions without full page reloads
- **Responsive**: Design mobile-first with Tailwind breakpoints

### Security
- **Authentication**: Always check user permissions before actions
- **File uploads**: Validate file types and sizes server-side
- **CSRF**: Use Django's CSRF protection on all forms
- **Input validation**: Sanitize all user inputs

### Testing
- **Framework**: Django TestCase with unittest.mock for external dependencies
- **Test data**: Create realistic test fixtures in setUp methods
- **Coverage**: Aim for high test coverage on business logic
- **Isolation**: Mock external services and time-dependent functions

### File Organization
- **Models**: Keep related models in same file, use clear relationships
- **Views**: Group related views together, use descriptive names
- **Utils**: Create utility modules for reusable functions
- **Tests**: Mirror source structure in tests directory

### Performance
- **Queries**: Optimize with select_related/prefetch_related
- **Caching**: Use Django's cache framework for expensive operations
- **Static files**: Ensure proper compression and caching headers
- **Background tasks**: Use Celery for long-running operations

### Error Handling
- **User-facing**: Provide clear, actionable error messages
- **Logging**: Log detailed error information for debugging
- **Graceful degradation**: Handle failures without breaking user experience
- **Validation**: Fail fast with clear validation messages