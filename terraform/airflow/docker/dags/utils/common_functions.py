"""
Common utility functions for Airflow DAGs.
These functions can be reused across different DAGs.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from airflow.models import Variable
from airflow.utils.email import send_email
from airflow.utils.context import Context

def get_bigquery_table_path(project_id: str, dataset_id: str, table_id: str) -> str:
    """
    Construct a fully qualified BigQuery table path.
    
    Args:
        project_id: GCP project ID
        dataset_id: BigQuery dataset ID
        table_id: BigQuery table ID
        
    Returns:
        str: Fully qualified table path
    """
    return f"`{project_id}.{dataset_id}.{table_id}`"

def get_airflow_variable(var_name: str, default: Any = None) -> Any:
    """
    Safely get an Airflow variable with a default value.
    
    Args:
        var_name: Name of the Airflow variable
        default: Default value if variable doesn't exist
        
    Returns:
        The variable value or default
    """
    try:
        return Variable.get(var_name)
    except KeyError:
        return default

def format_notification_email(
    context: Context,
    status: str,
    include_exception: bool = False
) -> Dict[str, str]:
    """
    Format email notification content for DAG execution.
    
    Args:
        context: Airflow context
        status: 'success' or 'failure'
        include_exception: Whether to include exception details
        
    Returns:
        Dict with subject and html_content
    """
    dag_id = context['dag'].dag_id
    task_id = context['task'].task_id
    execution_date = context['execution_date']
    
    subject = f'Airflow {status.title()}: {dag_id} - {task_id}'
    
    html_content = f"""
    <h3>DAG Execution {status.title()}</h3>
    <p><b>DAG:</b> {dag_id}</p>
    <p><b>Task:</b> {task_id}</p>
    <p><b>Execution Date:</b> {execution_date}</p>
    """
    
    if include_exception and 'exception' in context:
        html_content += f"<p><b>Exception:</b> {context['exception']}</p>"
    
    html_content += f"<p><b>Log URL:</b> <a href='{context['task_instance'].log_url}'>View Log</a></p>"
    
    return {
        'subject': subject,
        'html_content': html_content
    }

def send_notification(
    context: Context,
    status: str,
    email_list: list,
    include_exception: bool = False
) -> None:
    """
    Send email notification for DAG execution.
    
    Args:
        context: Airflow context
        status: 'success' or 'failure'
        email_list: List of email addresses
        include_exception: Whether to include exception details
    """
    email_content = format_notification_email(context, status, include_exception)
    
    send_email(
        to=email_list,
        subject=email_content['subject'],
        html_content=email_content['html_content']
    )

def get_data_interval(
    days_back: int = 30,
    start_date: Optional[datetime] = None
) -> Dict[str, datetime]:
    """
    Calculate data interval for processing.
    
    Args:
        days_back: Number of days to look back
        start_date: Optional start date (defaults to current date)
        
    Returns:
        Dict with start and end dates
    """
    end_date = start_date or datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    return {
        'start_date': start_date,
        'end_date': end_date
    }

def validate_traffic_data(traffic_count: int) -> bool:
    """
    Validate traffic data based on business rules.
    
    Args:
        traffic_count: Number of passengers
        
    Returns:
        bool: Whether the data is valid
    """
    # Example validation rules
    if traffic_count < 0:
        return False
    if traffic_count > 100000:  # Example threshold
        return False
    return True

def get_peak_period(hour: int) -> str:
    """
    Determine peak period based on hour.
    
    Args:
        hour: Hour of the day (0-23)
        
    Returns:
        str: Peak period classification
    """
    if 7 <= hour <= 9:
        return 'morning_peak'
    elif 17 <= hour <= 19:
        return 'evening_peak'
    return 'off_peak'

def get_day_type(date: datetime) -> str:
    """
    Determine if a date is a weekday or weekend.
    
    Args:
        date: Date to check
        
    Returns:
        str: 'weekday' or 'weekend'
    """
    day_of_week = date.weekday()
    return 'weekend' if day_of_week in [5, 6] else 'weekday' 