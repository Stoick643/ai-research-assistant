"""
WTForms for handling web forms and validation.
"""

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SelectMultipleField, IntegerField, BooleanField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class ResearchForm(FlaskForm):
    """Form for submitting new research requests."""
    
    topic = TextAreaField(
        'Research Topic',
        validators=[
            DataRequired(message='Please enter a research topic'),
            Length(min=10, max=1000, message='Topic must be between 10 and 1000 characters')
        ],
        render_kw={
            'placeholder': 'Enter your research topic (e.g., "AI trends in 2025", "Climate change impact on agriculture")',
            'rows': 3,
            'class': 'form-control'
        }
    )
    
    focus_areas = TextAreaField(
        'Focus Areas (Optional)',
        validators=[
            Optional(),
            Length(max=500, message='Focus areas must be less than 500 characters')
        ],
        render_kw={
            'placeholder': 'Specific areas to focus on (comma-separated)',
            'rows': 2,
            'class': 'form-control'
        }
    )
    
    source_language = SelectField(
        'Source Language',
        choices=[
            ('auto', 'Auto-detect'),
            ('en', 'English'),
            ('sl', 'Slovenian'),
            ('de', 'German'),
            ('fr', 'French'),
            ('es', 'Spanish'),
            ('it', 'Italian'),
            ('hr', 'Croatian'),
            ('sr', 'Serbian'),
            ('cs', 'Czech'),
            ('pl', 'Polish'),
            ('ru', 'Russian')
        ],
        default='auto',
        render_kw={'class': 'form-select'}
    )
    
    target_languages = SelectMultipleField(
        'Translation Languages',
        choices=[
            ('en', 'English'),
            ('sl', 'Slovenian'),
            ('de', 'German'),
            ('fr', 'French'),
            ('es', 'Spanish'),
            ('it', 'Italian'),
            ('hr', 'Croatian'),
            ('sr', 'Serbian'),
            ('cs', 'Czech'),
            ('pl', 'Polish'),
            ('ru', 'Russian')
        ],
        default=['en'],
        render_kw={'class': 'form-select', 'multiple': True}
    )
    
    max_queries = IntegerField(
        'Maximum Search Queries',
        validators=[
            NumberRange(min=1, max=20, message='Must be between 1 and 20')
        ],
        default=5,
        render_kw={'class': 'form-control'}
    )
    
    search_depth = SelectField(
        'Search Depth',
        choices=[
            ('basic', 'Basic'),
            ('advanced', 'Advanced')
        ],
        default='basic',
        render_kw={'class': 'form-select'}
    )
    
    enable_translation = BooleanField(
        'Enable Multi-language Translation',
        default=True,
        render_kw={'class': 'form-check-input'}
    )


class HistoryFilterForm(FlaskForm):
    """Form for filtering research history."""
    
    search = StringField(
        'Search',
        validators=[Optional()],
        render_kw={
            'placeholder': 'Search by topic or keywords...',
            'class': 'form-control'
        }
    )
    
    status = SelectField(
        'Status',
        choices=[
            ('', 'All'),
            ('completed', 'Completed'),
            ('in_progress', 'In Progress'),
            ('failed', 'Failed')
        ],
        default='',
        render_kw={'class': 'form-select'}
    )
    
    language = SelectField(
        'Language',
        choices=[
            ('', 'All Languages'),
            ('en', 'English'),
            ('sl', 'Slovenian'),
            ('de', 'German'),
            ('fr', 'French'),
            ('es', 'Spanish'),
            ('it', 'Italian')
        ],
        default='',
        render_kw={'class': 'form-select'}
    )
    
    date_range = SelectField(
        'Date Range',
        choices=[
            ('', 'All Time'),
            ('today', 'Today'),
            ('week', 'This Week'),
            ('month', 'This Month'),
            ('year', 'This Year')
        ],
        default='',
        render_kw={'class': 'form-select'}
    )