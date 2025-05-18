from nicegui import ui
import uvicorn
from api import app as fastapi_app
import aiohttp
import json
from datetime import datetime

# Global variable to store user data
current_user = None

# NiceGUI pages
@ui.page('/')
def index():
    with ui.card().classes('w-full max-w-md mx-auto mt-8'):
        ui.label('Welcome to Fitness First').classes('text-h4 q-mb-md')
        
        email = ui.input('Email').classes('w-full')
        password = ui.input('Password', password=True).classes('w-full')
        
        async def handle_login():
            global current_user
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        'http://localhost:3000/api/login',
                        json={'email': email.value, 'password': password.value}
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            current_user = data
                            ui.navigate.to(f'/{data["user_type"]}_dashboard')
                        else:
                            ui.notify('Invalid credentials', type='negative')
            except Exception as e:
                ui.notify(f'Error: {str(e)}', type='negative')
        
        ui.button('Login', on_click=handle_login).classes('w-full q-mt-md')

@ui.page('/admin_dashboard')
def admin_dashboard():
    global current_user
    if not current_user or current_user['user_type'] != 'admin':
        ui.navigate.to('/')
        return
    
    # Custom CSS for better styling
    ui.add_head_html('''
        <style>
            .dashboard-card {
                background: white;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                padding: 20px;
                margin: 10px;
            }
            .stat-card {
                background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
                color: white;
                border-radius: 8px;
                padding: 20px;
                margin: 10px;
            }
            .action-button {
                background: #4f46e5;
                color: white;
                border-radius: 6px;
                padding: 8px 16px;
                margin: 5px;
            }
            .action-button:hover {
                background: #4338ca;
            }
        </style>
    ''')
    
    with ui.card().classes('w-full max-w-6xl mx-auto mt-8'):
        # Header with welcome message and logout
        with ui.row().classes('w-full justify-between items-center mb-4'):
            ui.label(f'Welcome, {current_user["name"]}').classes('text-h4')
            ui.button('Logout', on_click=lambda: ui.navigate.to('/')).classes('action-button')
        
        # Quick stats row
        with ui.row().classes('w-full justify-between'):
            with ui.card().classes('stat-card w-1/4'):
                ui.label('Total Members').classes('text-h6')
                ui.label('150').classes('text-h3')
            with ui.card().classes('stat-card w-1/4'):
                ui.label('Active Coaches').classes('text-h6')
                ui.label('12').classes('text-h3')
            with ui.card().classes('stat-card w-1/4'):
                ui.label('Today\'s Sessions').classes('text-h6')
                ui.label('45').classes('text-h3')
            with ui.card().classes('stat-card w-1/4'):
                ui.label('Revenue').classes('text-h6')
                ui.label('$12,500').classes('text-h3')
        
        # Main content tabs
        with ui.tabs().classes('w-full mt-4') as tabs:
            gym_info = ui.tab('Gym Information')
            coaches = ui.tab('Manage Coaches')
            members = ui.tab('Manage Members')
            reports = ui.tab('Reports')
        
        with ui.tab_panels(tabs, value=gym_info).classes('w-full'):
            # Gym Information Panel
            with ui.tab_panel(gym_info):
                with ui.card().classes('dashboard-card'):
                    ui.label('Gym Information').classes('text-h5 q-mb-md')
                    
                    # Gym Details Form
                    with ui.column().classes('w-full gap-4'):
                        name = ui.input('Gym Name', value='Fitness First').classes('w-full')
                        address = ui.input('Address', value='123 Fitness Street').classes('w-full')
                        phone = ui.input('Phone', value='+1 234 567 8900').classes('w-full')
                        email = ui.input('Email', value='contact@fitnessfirst.com').classes('w-full')
                        
                        with ui.row().classes('w-full justify-end'):
                            ui.button('Save Changes', on_click=lambda: ui.notify('Changes saved!')).classes('action-button')
            
            # Coaches Management Panel
            with ui.tab_panel(coaches):
                with ui.card().classes('dashboard-card'):
                    with ui.row().classes('w-full justify-between items-center mb-4'):
                        ui.label('Manage Coaches').classes('text-h5')
                        ui.button('Add New Coach', on_click=lambda: ui.notify('Add coach functionality coming soon!')).classes('action-button')
                    
                    # Coaches Table
                    coaches_data = [
                        {'name': 'John Doe', 'email': 'john@fitnessfirst.com', 'specialization': 'Personal Training', 'status': 'Active'},
                        {'name': 'Jane Smith', 'email': 'jane@fitnessfirst.com', 'specialization': 'Yoga', 'status': 'Active'},
                        {'name': 'Mike Johnson', 'email': 'mike@fitnessfirst.com', 'specialization': 'CrossFit', 'status': 'Inactive'}
                    ]
                    
                    ui.aggrid({
                        'columnDefs': [
                            {'headerName': 'Name', 'field': 'name'},
                            {'headerName': 'Email', 'field': 'email'},
                            {'headerName': 'Specialization', 'field': 'specialization'},
                            {'headerName': 'Status', 'field': 'status'},
                            {
                                'headerName': 'Actions',
                                'field': 'actions',
                                'cellRenderer': 'buttonRenderer',
                                'cellRendererParams': {
                                    'buttons': [
                                        {'text': 'Edit', 'onClick': 'edit_coach'},
                                        {'text': 'Delete', 'onClick': 'delete_coach'}
                                    ]
                                }
                            }
                        ],
                        'rowData': coaches_data
                    }).classes('w-full h-64')
            
            # Members Management Panel
            with ui.tab_panel(members):
                with ui.card().classes('dashboard-card'):
                    with ui.row().classes('w-full justify-between items-center mb-4'):
                        ui.label('Manage Members').classes('text-h5')
                        ui.button('Add New Member', on_click=lambda: ui.notify('Add member functionality coming soon!')).classes('action-button')
                    
                    # Members Table
                    members_data = [
                        {'name': 'Alice Brown', 'email': 'alice@email.com', 'membership': 'Premium', 'join_date': '2024-01-15'},
                        {'name': 'Bob Wilson', 'email': 'bob@email.com', 'membership': 'Basic', 'join_date': '2024-02-01'},
                        {'name': 'Carol Davis', 'email': 'carol@email.com', 'membership': 'Premium', 'join_date': '2024-01-20'}
                    ]
                    
                    ui.aggrid({
                        'columnDefs': [
                            {'headerName': 'Name', 'field': 'name'},
                            {'headerName': 'Email', 'field': 'email'},
                            {'headerName': 'Membership Type', 'field': 'membership'},
                            {'headerName': 'Join Date', 'field': 'join_date'},
                            {
                                'headerName': 'Actions',
                                'field': 'actions',
                                'cellRenderer': 'buttonRenderer',
                                'cellRendererParams': {
                                    'buttons': [
                                        {'text': 'Edit', 'onClick': 'edit_member'},
                                        {'text': 'Delete', 'onClick': 'delete_member'}
                                    ]
                                }
                            }
                        ],
                        'rowData': members_data
                    }).classes('w-full h-64')
                    
                    def handle_edit_member(e):
                        ui.notify('Edit functionality coming soon!')
                    
                    def handle_delete_member(e):
                        ui.notify('Delete functionality coming soon!')
                    
                    members_table.on('edit_member', handle_edit_member)
                    members_table.on('delete_member', handle_delete_member)
            
            # Reports Panel
            with ui.tab_panel(reports):
                with ui.card().classes('dashboard-card'):
                    ui.label('Reports').classes('text-h5 q-mb-md')
                    
                    # Report Filters
                    with ui.row().classes('w-full gap-4 mb-4'):
                        report_type = ui.select(
                            ['Revenue Report', 'Membership Report', 'Coach Performance', 'Attendance Report'],
                            value='Revenue Report'
                        ).classes('w-1/3')
                        date_range = ui.select(
                            ['Last 7 Days', 'Last 30 Days', 'Last 90 Days', 'Custom Range'],
                            value='Last 30 Days'
                        ).classes('w-1/3')
                        ui.button('Generate Report', on_click=lambda: ui.notify('Report generation coming soon!')).classes('action-button')
                    
                    # Placeholder for report visualization
                    with ui.card().classes('w-full h-64 bg-gray-100 flex items-center justify-center'):
                        ui.label('Report visualization will appear here').classes('text-gray-500')

@ui.page('/coach_dashboard')
def coach_dashboard():
    global current_user
    if not current_user or current_user['user_type'] != 'coach':
        ui.navigate.to('/')
        return
    
    # Custom CSS for better styling
    ui.add_head_html('''
        <style>
            .dashboard-card {
                background: white;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                padding: 20px;
                margin: 10px;
            }
            .stat-card {
                background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
                color: white;
                border-radius: 8px;
                padding: 20px;
                margin: 10px;
            }
            .action-button {
                background: #4f46e5;
                color: white;
                border-radius: 6px;
                padding: 8px 16px;
                margin: 5px;
            }
            .action-button:hover {
                background: #4338ca;
            }
        </style>
    ''')
    
    with ui.card().classes('w-full max-w-6xl mx-auto mt-8'):
        # Header with welcome message and logout
        with ui.row().classes('w-full justify-between items-center mb-4'):
            ui.label(f'Welcome, {current_user["name"]}').classes('text-h4')
            ui.button('Logout', on_click=lambda: ui.navigate.to('/')).classes('action-button')
        
        # Quick stats row
        with ui.row().classes('w-full justify-between'):
            with ui.card().classes('stat-card w-1/3'):
                ui.label('Specialization').classes('text-h6')
                ui.label(current_user.get('specialization', 'N/A')).classes('text-h3')
            with ui.card().classes('stat-card w-1/3'):
                ui.label('Today\'s Sessions').classes('text-h6')
                today_sessions = ui.label('Loading...').classes('text-h3')
            with ui.card().classes('stat-card w-1/3'):
                ui.label('Total Members').classes('text-h6')
                total_members = ui.label('Loading...').classes('text-h3')
        
        # Main content tabs
        with ui.tabs().classes('w-full mt-4') as tabs:
            schedule = ui.tab('My Schedule')
            members = ui.tab('My Members')
            availability = ui.tab('Set Availability')
            sessions = ui.tab('Manage Sessions')
        
        with ui.tab_panels(tabs, value=schedule).classes('w-full'):
            # Schedule Panel
            with ui.tab_panel(schedule):
                with ui.card().classes('dashboard-card'):
                    ui.label('My Schedule').classes('text-h5 q-mb-md')
                    
                    # Schedule table
                    schedule_table = ui.aggrid({
                        'columnDefs': [
                            {'headerName': 'Date', 'field': 'session_date'},
                            {'headerName': 'Time', 'field': 'session_time'},
                            {'headerName': 'Member', 'field': 'member_name'},
                            {'headerName': 'Status', 'field': 'status'},
                            {
                                'headerName': 'Actions',
                                'field': 'actions',
                                'cellRenderer': 'buttonRenderer',
                                'cellRendererParams': {
                                    'buttons': [
                                        {'text': 'Complete', 'onClick': 'complete_session'},
                                        {'text': 'Cancel', 'onClick': 'cancel_session'}
                                    ]
                                }
                            }
                        ],
                        'rowData': []
                    }).classes('w-full h-64')
                    
                    # Load schedule data
                    async def load_schedule():
                        try:
                            async with aiohttp.ClientSession() as session:
                                async with session.get(f'http://localhost:3000/api/coach/{current_user["id"]}/schedule') as response:
                                    if response.status == 200:
                                        schedule = await response.json()
                                        schedule_table.options['rowData'] = schedule
                                        schedule_table.update()
                                        today = datetime.now().strftime('%Y-%m-%d')
                                        today_sessions.set_text(str(len([s for s in schedule if s['session_date'] == today])))
                        except Exception as e:
                            ui.notify(f'Error loading schedule: {str(e)}', type='negative')
                    
                    def handle_complete_session(e):
                        ui.notify('Complete session functionality coming soon!')
                    
                    def handle_cancel_session(e):
                        ui.notify('Cancel session functionality coming soon!')
                    
                    schedule_table.on('complete_session', handle_complete_session)
                    schedule_table.on('cancel_session', handle_cancel_session)
                    
                    ui.button('Refresh', on_click=load_schedule).classes('action-button')
            
            # Members Panel
            with ui.tab_panel(members):
                with ui.card().classes('dashboard-card'):
                    ui.label('My Members').classes('text-h5 q-mb-md')
                    
                    # Members table
                    members_table = ui.aggrid({
                        'columnDefs': [
                            {'headerName': 'Name', 'field': 'name'},
                            {'headerName': 'Email', 'field': 'email'},
                            {'headerName': 'Membership Type', 'field': 'membership_type'},
                            {'headerName': 'Join Date', 'field': 'join_date'},
                            {
                                'headerName': 'Actions',
                                'field': 'actions',
                                'cellRenderer': 'buttonRenderer',
                                'cellRendererParams': {
                                    'buttons': [
                                        {'text': 'View Progress', 'onClick': 'view_progress'},
                                        {'text': 'Message', 'onClick': 'message_member'}
                                    ]
                                }
                            }
                        ],
                        'rowData': []
                    }).classes('w-full h-64')
                    
                    # Load members data
                    async def load_members():
                        try:
                            async with aiohttp.ClientSession() as session:
                                async with session.get(f'http://localhost:3000/api/coach/{current_user["id"]}/members') as response:
                                    if response.status == 200:
                                        members = await response.json()
                                        members_table.options['rowData'] = members
                                        members_table.update()
                                        total_members.set_text(str(len(members)))
                        except Exception as e:
                            ui.notify(f'Error loading members: {str(e)}', type='negative')
                    
                    def handle_view_progress(e):
                        ui.notify('View progress functionality coming soon!')
                    
                    def handle_message_member(e):
                        ui.notify('Message functionality coming soon!')
                    
                    members_table.on('view_progress', handle_view_progress)
                    members_table.on('message_member', handle_message_member)
                    
                    ui.button('Refresh', on_click=load_members).classes('action-button')
            
            # Availability Panel
            with ui.tab_panel(availability):
                with ui.card().classes('dashboard-card'):
                    ui.label('Set Availability').classes('text-h5 q-mb-md')
                    
                    # Availability form
                    with ui.column().classes('w-full gap-4'):
                        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                        for day in days:
                            with ui.row().classes('w-full items-center gap-4'):
                                ui.checkbox(day).classes('w-1/4')
                                ui.time('Start Time').classes('w-1/4')
                                ui.time('End Time').classes('w-1/4')
                        
                        with ui.row().classes('w-full justify-end'):
                            ui.button('Save Availability', on_click=lambda: ui.notify('Availability saving coming soon!')).classes('action-button')
            
            # Sessions Panel
            with ui.tab_panel(sessions):
                with ui.card().classes('dashboard-card'):
                    ui.label('Manage Sessions').classes('text-h5 q-mb-md')
                    
                    # Session management form
                    with ui.column().classes('w-full gap-4'):
                        member = ui.select(['Select Member'], value='Select Member').classes('w-full')
                        date = ui.date('Session Date').classes('w-full')
                        time = ui.time('Session Time').classes('w-full')
                        duration = ui.select(
                            ['30 minutes', '45 minutes', '60 minutes', '90 minutes'],
                            value='60 minutes'
                        ).classes('w-full')
                        notes = ui.textarea('Session Notes').classes('w-full')
                        
                        with ui.row().classes('w-full justify-end'):
                            ui.button('Schedule Session', on_click=lambda: ui.notify('Session scheduling coming soon!')).classes('action-button')

@ui.page('/member_dashboard')
def member_dashboard():
    global current_user
    if not current_user or current_user['user_type'] != 'member':
        ui.navigate.to('/')
        return
    
    # Custom CSS for better styling
    ui.add_head_html('''
        <style>
            .dashboard-card {
                background: white;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                padding: 20px;
                margin: 10px;
            }
            .stat-card {
                background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
                color: white;
                border-radius: 8px;
                padding: 20px;
                margin: 10px;
            }
            .action-button {
                background: #4f46e5;
                color: white;
                border-radius: 6px;
                padding: 8px 16px;
                margin: 5px;
            }
            .action-button:hover {
                background: #4338ca;
            }
        </style>
    ''')
    
    with ui.card().classes('w-full max-w-6xl mx-auto mt-8'):
        # Header with welcome message and logout
        with ui.row().classes('w-full justify-between items-center mb-4'):
            ui.label(f'Welcome, {current_user["name"]}').classes('text-h4')
            ui.button('Logout', on_click=lambda: ui.navigate.to('/')).classes('action-button')
        
        # Quick stats row
        with ui.row().classes('w-full justify-between'):
            with ui.card().classes('stat-card w-1/3'):
                ui.label('Membership Type').classes('text-h6')
                ui.label(current_user.get('membership_type', 'Basic')).classes('text-h3')
            with ui.card().classes('stat-card w-1/3'):
                ui.label('Upcoming Sessions').classes('text-h6')
                upcoming_sessions = ui.label('Loading...').classes('text-h3')
            with ui.card().classes('stat-card w-1/3'):
                ui.label('Total Sessions').classes('text-h6')
                total_sessions = ui.label('Loading...').classes('text-h3')
        
        # Main content tabs
        with ui.tabs().classes('w-full mt-4') as tabs:
            book = ui.tab('Book Session')
            schedule = ui.tab('My Schedule')
            coach = ui.tab('My Coach')
            availability = ui.tab('Set Availability')
        
        with ui.tab_panels(tabs, value=book).classes('w-full'):
            # Book Session Panel
            with ui.tab_panel(book):
                with ui.card().classes('dashboard-card'):
                    ui.label('Book a Session').classes('text-h5 q-mb-md')
                    
                    # Session booking form
                    with ui.column().classes('w-full gap-4'):
                        date = ui.date('Session Date').classes('w-full')
                        time = ui.time('Session Time').classes('w-full')
                        duration = ui.select(
                            ['30 minutes', '45 minutes', '60 minutes', '90 minutes'],
                            value='60 minutes'
                        ).classes('w-full')
                        
                        with ui.row().classes('w-full justify-end'):
                            ui.button('Book Session', on_click=lambda: ui.notify('Booking functionality coming soon!')).classes('action-button')
            
            # Schedule Panel
            with ui.tab_panel(schedule):
                with ui.card().classes('dashboard-card'):
                    ui.label('My Schedule').classes('text-h5 q-mb-md')
                    
                    # Sessions table
                    sessions_table = ui.aggrid({
                        'columnDefs': [
                            {'headerName': 'Date', 'field': 'session_date'},
                            {'headerName': 'Time', 'field': 'session_time'},
                            {'headerName': 'Coach', 'field': 'coach_name'},
                            {'headerName': 'Status', 'field': 'status'},
                            {
                                'headerName': 'Actions',
                                'field': 'actions',
                                'cellRenderer': 'buttonRenderer',
                                'cellRendererParams': {
                                    'buttons': [
                                        {'text': 'Cancel', 'onClick': 'cancel_session'}
                                    ]
                                }
                            }
                        ],
                        'rowData': []
                    }).classes('w-full h-64')
                    
                    def handle_cancel_session(e):
                        ui.notify('Cancel functionality coming soon!')
                    
                    sessions_table.on('cancel_session', handle_cancel_session)
                    
                    # Load sessions data
                    async def load_sessions():
                        try:
                            async with aiohttp.ClientSession() as session:
                                async with session.get(f'http://localhost:3000/api/member/{current_user["id"]}/sessions') as response:
                                    if response.status == 200:
                                        sessions = await response.json()
                                        sessions_table.options['rowData'] = sessions
                                        sessions_table.update()
                                        upcoming_sessions.set_text(str(len([s for s in sessions if s['status'] == 'scheduled'])))
                                        total_sessions.set_text(str(len(sessions)))
                        except Exception as e:
                            ui.notify(f'Error loading sessions: {str(e)}', type='negative')
                    
                    ui.button('Refresh', on_click=load_sessions).classes('action-button')
            
            # Coach Panel
            with ui.tab_panel(coach):
                with ui.card().classes('dashboard-card'):
                    ui.label('My Coach').classes('text-h5 q-mb-md')
                    
                    # Coach information
                    coach_info = ui.column().classes('w-full gap-4')
                    
                    async def load_coach():
                        try:
                            async with aiohttp.ClientSession() as session:
                                async with session.get(f'http://localhost:3000/api/member/{current_user["id"]}/coach') as response:
                                    if response.status == 200:
                                        coach = await response.json()
                                        if 'detail' in coach:
                                            coach_info.clear()
                                            with coach_info:
                                                ui.label('No coach assigned yet').classes('text-h6')
                                        else:
                                            coach_info.clear()
                                            with coach_info:
                                                ui.label(f'Name: {coach["name"]}').classes('text-h6')
                                                ui.label(f'Email: {coach["email"]}').classes('text-h6')
                                                ui.label(f'Specialization: {coach.get("specialization", "N/A")}').classes('text-h6')
                        except Exception as e:
                            ui.notify(f'Error loading coach: {str(e)}', type='negative')
                    
                    ui.button('Refresh', on_click=load_coach).classes('action-button')
            
            # Availability Panel
            with ui.tab_panel(availability):
                with ui.card().classes('dashboard-card'):
                    ui.label('Set Availability').classes('text-h5 q-mb-md')
                    
                    # Availability form
                    with ui.column().classes('w-full gap-4'):
                        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                        for day in days:
                            with ui.row().classes('w-full items-center gap-4'):
                                ui.checkbox(day).classes('w-1/4')
                                ui.time('Start Time').classes('w-1/4')
                                ui.time('End Time').classes('w-1/4')
                        
                        with ui.row().classes('w-full justify-end'):
                            ui.button('Save Availability', on_click=lambda: ui.notify('Availability saving coming soon!')).classes('action-button')

@ui.page('/gym_dashboard')
def gym_dashboard():
    global current_user
    if not current_user or current_user['user_type'] != 'gym':
        ui.navigate.to('/')
        return
    
    # Custom CSS for better styling
    ui.add_head_html('''
        <style>
            .dashboard-card {
                background: white;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                padding: 20px;
                margin: 10px;
            }
            .stat-card {
                background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
                color: white;
                border-radius: 8px;
                padding: 20px;
                margin: 10px;
            }
            .action-button {
                background: #4f46e5;
                color: white;
                border-radius: 6px;
                padding: 8px 16px;
                margin: 5px;
            }
            .action-button:hover {
                background: #4338ca;
            }
        </style>
    ''')
    
    with ui.card().classes('w-full max-w-6xl mx-auto mt-8'):
        # Header with welcome message and logout
        with ui.row().classes('w-full justify-between items-center mb-4'):
            ui.label(f'Welcome, {current_user["name"]}').classes('text-h4')
            ui.button('Logout', on_click=lambda: ui.navigate.to('/')).classes('action-button')
        
        # Quick stats row
        with ui.row().classes('w-full justify-between'):
            with ui.card().classes('stat-card w-1/3'):
                ui.label('Total Members').classes('text-h6')
                total_members = ui.label('Loading...').classes('text-h3')
            with ui.card().classes('stat-card w-1/3'):
                ui.label('Active Coaches').classes('text-h6')
                active_coaches = ui.label('Loading...').classes('text-h3')
            with ui.card().classes('stat-card w-1/3'):
                ui.label('Today\'s Sessions').classes('text-h6')
                today_sessions = ui.label('Loading...').classes('text-h3')
        
        # Main content tabs
        with ui.tabs().classes('w-full mt-4') as tabs:
            coaches = ui.tab('Manage Coaches')
            members = ui.tab('Manage Members')
            sessions = ui.tab('View Sessions')
            settings = ui.tab('Gym Settings')
        
        with ui.tab_panels(tabs, value=coaches).classes('w-full'):
            # Coaches Panel
            with ui.tab_panel(coaches):
                with ui.card().classes('dashboard-card'):
                    with ui.row().classes('w-full justify-between items-center mb-4'):
                        ui.label('Manage Coaches').classes('text-h5')
                        ui.button('Add New Coach', on_click=lambda: ui.notify('Add coach functionality coming soon!')).classes('action-button')
                    
                    # Coaches table
                    coaches_table = ui.aggrid({
                        'columnDefs': [
                            {'headerName': 'Name', 'field': 'name'},
                            {'headerName': 'Email', 'field': 'email'},
                            {'headerName': 'Specialization', 'field': 'specialization'},
                            {'headerName': 'Status', 'field': 'status'},
                            {'headerName': 'Assigned Members', 'field': 'assigned_members'},
                            {'headerName': 'Total Sessions', 'field': 'total_sessions'},
                            {
                                'headerName': 'Actions',
                                'field': 'actions',
                                'cellRenderer': 'buttonRenderer',
                                'cellRendererParams': {
                                    'buttons': [
                                        {'text': 'Edit', 'onClick': 'edit_coach'},
                                        {'text': 'Delete', 'onClick': 'delete_coach'}
                                    ]
                                }
                            }
                        ],
                        'rowData': []
                    }).classes('w-full h-64')
                    
                    # Load coaches data
                    async def load_coaches():
                        try:
                            async with aiohttp.ClientSession() as session:
                                async with session.get(f'http://localhost:3000/api/gym/{current_user["id"]}/coaches') as response:
                                    if response.status == 200:
                                        coaches = await response.json()
                                        coaches_table.options['rowData'] = coaches
                                        coaches_table.update()
                                        active_coaches.set_text(str(len([c for c in coaches if c.get('status') == 'Active'])))
                        except Exception as e:
                            ui.notify(f'Error loading coaches: {str(e)}', type='negative')
                    
                    def handle_edit_coach(e):
                        ui.notify('Edit coach functionality coming soon!')
                    
                    def handle_delete_coach(e):
                        ui.notify('Delete coach functionality coming soon!')
                    
                    coaches_table.on('edit_coach', handle_edit_coach)
                    coaches_table.on('delete_coach', handle_delete_coach)
                    
                    ui.button('Refresh', on_click=load_coaches).classes('action-button')
                    
                    # Add coach form
                    with ui.dialog() as add_coach_dialog, ui.card():
                        ui.label('Add New Coach').classes('text-h5 q-mb-md')
                        name = ui.input('Name').classes('w-full')
                        email = ui.input('Email').classes('w-full')
                        password = ui.input('Password', password=True).classes('w-full')
                        specialization = ui.input('Specialization').classes('w-full')
                        
                        async def handle_add_coach():
                            try:
                                async with aiohttp.ClientSession() as session:
                                    async with session.post(
                                        f'http://localhost:3000/api/gym/{current_user["id"]}/coach',
                                        json={
                                            'name': name.value,
                                            'email': email.value,
                                            'password': password.value,
                                            'specialization': specialization.value
                                        }
                                    ) as response:
                                        if response.status == 200:
                                            ui.notify('Coach added successfully!')
                                            add_coach_dialog.close()
                                            await load_coaches()
                                        else:
                                            ui.notify('Error adding coach', type='negative')
                            except Exception as e:
                                ui.notify(f'Error: {str(e)}', type='negative')
                        
                        with ui.row().classes('w-full justify-end'):
                            ui.button('Cancel', on_click=add_coach_dialog.close).classes('action-button')
                            ui.button('Add Coach', on_click=handle_add_coach).classes('action-button')
                    
                    ui.button('Add New Coach', on_click=add_coach_dialog.open).classes('action-button')
            
            # Members Panel
            with ui.tab_panel(members):
                with ui.card().classes('dashboard-card'):
                    with ui.row().classes('w-full justify-between items-center mb-4'):
                        ui.label('Manage Members').classes('text-h5')
                        ui.button('Add New Member', on_click=lambda: ui.notify('Add member functionality coming soon!')).classes('action-button')
                    
                    # Members table
                    members_table = ui.aggrid({
                        'columnDefs': [
                            {'headerName': 'Name', 'field': 'name'},
                            {'headerName': 'Email', 'field': 'email'},
                            {'headerName': 'Membership Type', 'field': 'membership_type'},
                            {'headerName': 'Coach', 'field': 'coach_name'},
                            {'headerName': 'Total Sessions', 'field': 'total_sessions'},
                            {
                                'headerName': 'Actions',
                                'field': 'actions',
                                'cellRenderer': 'buttonRenderer',
                                'cellRendererParams': {
                                    'buttons': [
                                        {'text': 'Assign Coach', 'onClick': 'assign_coach'},
                                        {'text': 'Edit', 'onClick': 'edit_member'},
                                        {'text': 'Delete', 'onClick': 'delete_member'}
                                    ]
                                }
                            }
                        ],
                        'rowData': []
                    }).classes('w-full h-64')
                    
                    # Load members data
                    async def load_members():
                        try:
                            async with aiohttp.ClientSession() as session:
                                async with session.get(f'http://localhost:3000/api/gym/{current_user["id"]}/members') as response:
                                    if response.status == 200:
                                        members = await response.json()
                                        members_table.options['rowData'] = members
                                        members_table.update()
                                        total_members.set_text(str(len(members)))
                        except Exception as e:
                            ui.notify(f'Error loading members: {str(e)}', type='negative')
                    
                    def handle_assign_coach(e):
                        ui.notify('Assign coach functionality coming soon!')
                    
                    def handle_edit_member(e):
                        ui.notify('Edit member functionality coming soon!')
                    
                    def handle_delete_member(e):
                        ui.notify('Delete member functionality coming soon!')
                    
                    members_table.on('assign_coach', handle_assign_coach)
                    members_table.on('edit_member', handle_edit_member)
                    members_table.on('delete_member', handle_delete_member)
                    
                    ui.button('Refresh', on_click=load_members).classes('action-button')
            
            # Sessions Panel
            with ui.tab_panel(sessions):
                with ui.card().classes('dashboard-card'):
                    ui.label('View Sessions').classes('text-h5 q-mb-md')
                    
                    # Sessions table
                    sessions_table = ui.aggrid({
                        'columnDefs': [
                            {'headerName': 'Date', 'field': 'session_date'},
                            {'headerName': 'Time', 'field': 'session_time'},
                            {'headerName': 'Coach', 'field': 'coach_name'},
                            {'headerName': 'Member', 'field': 'member_name'},
                            {'headerName': 'Status', 'field': 'status'}
                        ],
                        'rowData': []
                    }).classes('w-full h-64')
                    
                    # Load sessions data
                    async def load_sessions():
                        try:
                            async with aiohttp.ClientSession() as session:
                                async with session.get(f'http://localhost:3000/api/gym/{current_user["id"]}/sessions') as response:
                                    if response.status == 200:
                                        sessions = await response.json()
                                        sessions_table.options['rowData'] = sessions
                                        sessions_table.update()
                                        today = datetime.now().strftime('%Y-%m-%d')
                                        today_sessions.set_text(str(len([s for s in sessions if s['session_date'] == today])))
                        except Exception as e:
                            ui.notify(f'Error loading sessions: {str(e)}', type='negative')
                    
                    ui.button('Refresh', on_click=load_sessions).classes('action-button')
            
            # Settings Panel
            with ui.tab_panel(settings):
                with ui.card().classes('dashboard-card'):
                    ui.label('Gym Settings').classes('text-h5 q-mb-md')
                    
                    # Settings form
                    with ui.column().classes('w-full gap-4'):
                        name = ui.input('Gym Name', value=current_user.get('name', '')).classes('w-full')
                        email = ui.input('Email', value=current_user.get('email', '')).classes('w-full')
                        address = ui.input('Address', value=current_user.get('address', '')).classes('w-full')
                        phone = ui.input('Phone', value=current_user.get('phone', '')).classes('w-full')
                        
                        with ui.row().classes('w-full justify-end'):
                            ui.button('Save Changes', on_click=lambda: ui.notify('Settings saving coming soon!')).classes('action-button')

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title='Fitness First - Training Management', port=8080)
