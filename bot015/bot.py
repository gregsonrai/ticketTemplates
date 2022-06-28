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

    remove_tag_value = {"hasTag":{"remove":["srn:sonrai::Tag/SonraiDataClassification:Sensitive"]}}
    # Remove "Sensitive" tag from the resource if it exists
    query = '''
        mutation removeTag($resourceSrn: ID!, $value: ResourceUpdater!) {
          UpdateResource(srn: $resourceSrn, value: $value) {
            resourceId
            __typename
          }
        }
    '''

    print("Attempting to remove SonraiDataClassification:Sensitive tag from " + object_srn)
    variables = { "resourceSrn": object_srn, "value": remove_tag_value }

    try: 
        response = ctx.graphql_client().query(query, variables)
        print("Successfully removed tag")
   
    except Exception as e:
        print("Could not remove tag.  It may never have existed!  Bravely continuing on")

    tag_key = "SonraiDataClassification"
    tag_value = "Highly Sensitive"

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

    print("Adding " + tag_key + ":" + "tag_value" + " tag to " + object_srn)
    variables = { "srn": object_srn, "key": tag_key, "value": tag_value }
    response = ctx.graphql_client().query(query, variables)
