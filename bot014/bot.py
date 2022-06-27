import re
import sys
import logging
import sonrai.platform.aws.arn
import datetime
from datetime import timedelta

def run(ctx):
    # Get the ticket data from the context
    ticket = ctx.config.get('data').get('ticket')
    ticket_srn = ticket.get("srn")

    # SRN of the resource in the ticket
    object_srn = ctx.resource_srn

    tag_key = "SonraiDataClassification"
    tag_value = "Sensitive"

    # Add tag to the resource
    query = '''
        mutation addTag($key: String, $value: String, $srn: ID) {
          AddTag(value: {key: $key, value: $value, tagsEntity: {add: [$srn]}}) {
            srn
            key
            value
            __typename
          }
        }
    '''
    variables = { "srn": object_srn, "key": tag_key, "value": tag_value }
    response = ctx.graphql_client().query(query, variables)
