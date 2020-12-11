import re
import sys
import logging
import datetime
from datetime import timedelta

def run(ctx):
    # Get the ticket data from the context
    ticket = ctx.config.get('data').get('ticket')
    ticket_srn = ticket.get("srn")

    logging.info('Hello World!')

    query = '''
        mutation reopenTicket($srn: String) {
            ReopenTickets(input: {srns: [$srn]}) {   
              successCount
              failureCount
              __typename
            }
        }
    '''
    variables = { "srn": ticket_srn }
    response = ctx.graphql_client().query(query, variables)
