import PureCloudPlatformApiSdk, requests, json, os, csv, oauth2
from PureCloudPlatformApiSdk.rest import ApiException

with open('configuration.json') as config_file:
    config = json.load(config_file)

os.environ['REQUESTS_CA_BUNDLE'] = os.path.join(os.getcwd(), config['ca_cert_file'])

PureCloudPlatformApiSdk.configuration.host = config['api_host']
PureCloudPlatformApiSdk.configuration.ssl_ca_cert = os.path.join(os.getcwd(), config['ca_cert_file'])
PureCloudPlatformApiSdk.configuration.access_token = oauth2.get_oauth2_token(config)

if not PureCloudPlatformApiSdk.configuration.access_token:
    print('Authorization failed.')
    exit(1)

with open('query.json') as query_file:
    query_json = json.load(query_file)

def BuildAnalyticsQuery(query_json):
    query = PureCloudPlatformApiSdk.ConversationQuery()
    for k in query.attribute_map:
        setattr(query, k, query_json.get(query.attribute_map[k]))
    if not query.paging:
        query.paging = { "pageSize": 25, "pageNumber": 1 }
    return query

def ExportParticipant(p):
    if config['include_no_attribute_results']:
        return p.purpose in config['participant_purpose']
    else:
        return p.purpose in config['participant_purpose'] and p.attributes

def GetQueueIdMap():
    queue_id_map = {}
    routing_api = PureCloudPlatformApiSdk.RoutingApi()
    done = False
    page_number = 1
    while not done:
        res = routing_api.get_queues(page_number=page_number)
        print('Got queues page {0} of {1}'.format(page_number, res.page_count))
        for q in res.entities:
            queue_id_map[q.id] = q
        done = (page_number >= res.page_count)
        page_number += 1
    print('Queues found:', len(queue_id_map))
    return queue_id_map

def GetUserIdMap():
    user_id_map = {}
    users_api = PureCloudPlatformApiSdk.UsersApi()
    done = False
    page_number = 1
    while not done:
        res = users_api.get_users(page_number=page_number)
        print('Got users page {0} of {1}'.format(page_number, res.page_count))
        for u in res.entities:
            user_id_map[u.id] = u
        done = (page_number >= res.page_count)
        page_number += 1
    print('Users found:', len(user_id_map))
    return user_id_map


# GLOBALS #############################################################################################################
analytics_api = PureCloudPlatformApiSdk.AnalyticsApi()
analytics_conversations = []
full_conversations = []

queue_id_map = GetQueueIdMap()
user_id_map = GetUserIdMap()
#######################################################################################################################

try:
    query = BuildAnalyticsQuery(query_json)
    analytics_response = analytics_api.post_conversations_details_query(query)

    while(analytics_response.conversations):
        print('Number of conversations:', len(analytics_response.conversations))
        analytics_conversations.extend([c for c in analytics_response.conversations])
        query.paging['pageNumber'] += 1
        analytics_response = analytics_api.post_conversations_details_query(query)

    count = len(analytics_conversations)
    conversations_api = PureCloudPlatformApiSdk.ConversationsApi()
    for i, convo in enumerate(analytics_conversations):
        print('GET conversation {0} of {1} (id {2})'.format(i + 1, count, convo.conversation_id))
        full_convo = conversations_api.get_conversation_id(convo.conversation_id)
        full_conversations.append(full_convo)

    attributes_set = set()
    results = []
    for c in full_conversations:
        for p in c.participants:
            if ExportParticipant(p):
                queue = queue_id_map.get(p.queue_id)
                user = user_id_map.get(p.user_id)

                result = {
                    'conversation_id': c.id,
                    'participant_id': p.id,
                    'participant_name': p.name,
                    'participant_purpose': p.purpose,
                    'participant_type': p.participant_type,
                    'queue_id': p.queue_id,
                    'queue_name': queue.name if queue else None,
                    'participant_ani': p.ani,
                    'participant_dnis': p.dnis,
                    'user_id': p.user_id,
                    'user_name': user.name if user else None,
                    'user_email': user.email if user else None
                }

                for key, value in p.attributes.items():
                    result[key] = value
                    attributes_set.add(key)
                results.append(result)

    # Set of "base" field names for field columns before sorted attribute list
    fieldnames = ['conversation_id','participant_id','participant_name','participant_purpose','participant_type',
                  'queue_id','queue_name','participant_ani','participant_dnis','user_id','user_name', 'user_email']
    fieldnames.extend(sorted(attributes_set))

    with open('py-purecloud-participant-data.csv', 'w') as outfile:
        csvwriter = csv.DictWriter(outfile, delimiter=',', lineterminator='\n', fieldnames=fieldnames)
        csvwriter.writeheader()
        csvwriter.writerows(results)

except ApiException as exc:
    print('ApiException: {0}\n'.format(exc))

print("Exiting...")
