import datetime
import argparse
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Define Scopes and Organization Calendar ID
SCOPES = ['www.googleapis.com']
ORG_CALENDAR_ID = 'your_org_calendar_id@group.calendar.google.com'

def get_calendar_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('calendar', 'v3', credentials=creds)

def list_slots(service):
    """View available slots on the organizational calendar."""
    now = datetime.datetime.utcnow().isoformat() + 'Z'
    events_result = service.events().list(calendarId=ORG_CALENDAR_ID, timeMin=now,
                                        singleEvents=True, orderBy='startTime').execute()
    events = events_result.get('items', [])
    for event in events:
        if "Available" in event.get('summary', ''):
            print(f"ID: {event['id']} | {event['summary']} | Start: {event['start'].get('dateTime')}")

def book_appointment(service, event_id, student_email):
    """Student requests help: updates Org, Student, and (later) Tutor calendars."""
    event = service.events().get(calendarId=ORG_CALENDAR_ID, eventId=event_id).execute()
    event['summary'] = f"Tutoring: {student_email}"
    event['attendees'] = [{'email': student_email}]
    
    # Update Org Calendar and automatically invite Student (personal calendar reflect)
    updated_event = service.events().update(calendarId=ORG_CALENDAR_ID, eventId=event_id, 
                                            body=event, sendUpdates='all').execute()
    print(f"Booked! Event updated: {updated_event.get('htmlLink')}")

def volunteer_to_teach(service, event_id, tutor_email):
    """Tutor joins an existing student request."""
    event = service.events().get(calendarId=ORG_CALENDAR_ID, eventId=event_id).execute()
    attendees = event.get('attendees', [])
    attendees.append({'email': tutor_email})
    event['attendees'] = attendees
    
    service.events().update(calendarId=ORG_CALENDAR_ID, eventId=event_id, 
                            body=event, sendUpdates='all').execute()
    print(f"Tutor {tutor_email} added to session.")

#cancel booking without checking if someone has accepted
def cancel_booking(service, event_id):
    """Cancels the booking and reverts slot to 'Available'."""
    event = service.events().get(calendarId=ORG_CALENDAR_ID, eventId=event_id).execute()
    event['summary'] = "Available Slot"
    event['attendees'] = []
    service.events().update(calendarId=ORG_CALENDAR_ID, eventId=event_id, 
                            body=event, sendUpdates='all').execute()
    print("Booking cancelled and slot reset.")

#only allows cancelation no one has accepted
def cancel_booking_ifonly(event_id, user_email, user_type):
    """
    Cancels a booking if the relevant counterparty has not accepted.
    A student can cancel if a volunteer hasn't accepted.
    A volunteer can cancel if a student hasn't accepted.
    """
    service = get_calendar_service()

    try:
        # Retrieve the event details
        event = service.events().get(calendarId=CALENDAR_ID, eventId=event_id).execute()
        attendees = event.get('attendees', [])
        
        student_accepted = False
        volunteer_accepted = False
        
        # Check the response status of all attendees
        for attendee in attendees:
            status = attendee.get('responseStatus')
            # For this logic, we assume we know which email belongs to which role beforehand.
            # A more robust system would involve storing roles in an external DB or extended props.
            # Here, let's assume we can identify based on provided user_email for the action
            # and another specific email for the counterparty (e.g., a known volunteer manager email).
            # The prompt implies the "organization's calendar" manages both.

            # Simple logic: If any attendee other than the acting user has 'accepted' status, prevent cancellation.
            if attendee.get('email') != user_email and status == 'accepted':
                 print(f"Cancellation blocked: Counterparty ({attendee.get('email')}) has already accepted the booking.")
                 return
            
        # If the conditions are met (no one else accepted, or only pending/declined), cancel the event.
        service.events().delete(calendarId=CALENDAR_ID, eventId=event_id, sendUpdates='all').execute()
        print(f"Event {event_id} has been cancelled successfully by {user_email} (as {user_type}). All guests notified.")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Tutor/Student Calendar CLI')
    parser.add_argument('action', choices=['list', 'book', 'volunteer', 'cancel'])
    parser.add_argument('--id', help='Event ID for booking/canceling')
    parser.add_argument('--email', help='Email of student or tutor')
    
    args = parser.parse_args()
    service = get_calendar_service()

    if args.action == 'list':
        list_slots(service)
    elif args.action == 'book':
        book_appointment(service, args.id, args.email)
    elif args.action == 'volunteer':
        volunteer_to_teach(service, args.id, args.email)
    elif args.action == 'cancel':
        cancel_booking(service, args.id)
