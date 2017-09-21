import PureCloudPlatformClientV2, requests, json, os, csv, oauth2, time, collections
from PureCloudPlatformClientV2.rest import ApiException

with open('configuration.json') as config_file:
    config = json.load(config_file)

os.environ['REQUESTS_CA_BUNDLE'] = os.path.join(os.getcwd(), config['ca_cert_file'])

PureCloudPlatformClientV2.configuration.host = config['api_host']
PureCloudPlatformClientV2.configuration.ssl_ca_cert = os.path.join(os.getcwd(), config['ca_cert_file'])
PureCloudPlatformClientV2.configuration.access_token = oauth2.get_oauth2_token(config)

if not PureCloudPlatformClientV2.configuration.access_token:
    print('Authorization failed.')
    exit(1)

auth_header = {'Authorization': 'bearer ' + PureCloudPlatformClientV2.configuration.access_token}

with open('queries.json') as query_file:
    queries_json = json.load(query_file)


def BuildAnalyticsQuery(query_json):
    query = PureCloudPlatformClientV2.ConversationQuery()
    for k in query.attribute_map:
        setattr(query, k, query_json.get(query.attribute_map[k]))
    if not query.paging:
        query.paging = {"pageSize": 100, "pageNumber": 1}
    return query


def ExportParticipant(p):
    if config['include_no_attribute_results']:
        return p.purpose in config['participant_purpose']
    else:
        return p.purpose in config['participant_purpose'] and p.attributes


def GetQueueIdMap():
    queue_id_map = {}
    routing_api = PureCloudPlatformClientV2.RoutingApi()
    done = False
    page_number = 1
    while not done:
        res = routing_api.get_routing_queues(page_number=page_number)
        print('Got queues page {0} of {1}'.format(page_number, res.page_count))
        for q in res.entities:
            queue_id_map[q.id] = q
        done = (page_number >= res.page_count)
        page_number += 1
    print('Queues found:', len(queue_id_map))
    return queue_id_map


def GetUserIdMap():
    user_id_map = {}
    users_api = PureCloudPlatformClientV2.UsersApi()
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

def flatten_json(y):
    out = {}
    def flatten(x, name=''):
        if type(x) is dict:
            for a in x:
                flatten(x[a], name + a + '_')
        elif type(x) is list:
            i = 0
            for a in x:
                flatten(a, name + str(i) + '_')
                i += 1
        else:
            out[name[:-1]] = x
    flatten(y)
    return out

def GetFlattenedConversations(conversations):
    flattened_convos = []
    for convo in conversations:
        flat = flatten_json(convo)
        flattened_convos.append(flat)
    return flattened_convos

# GLOBALS #############################################################################################################
analytics_api = PureCloudPlatformClientV2.AnalyticsApi()
analytics_conversations = collections.OrderedDict()
full_conversations = []

### FIXME - TEMP UNTIL PYTHON SDK CONVERSATION SERIALIZATION BUG FIX ###
full_conversations_json = []
############################

queue_id_map = GetQueueIdMap()
user_id_map = GetUserIdMap()
#######################################################################################################################

try:
    for i, query in enumerate(queries_json):
        query = BuildAnalyticsQuery(query)
        analytics_response = analytics_api.post_analytics_conversations_details_query(query)

        while (analytics_response.conversations):
            print('Query #' + str(i), 'conversations:', len(analytics_response.conversations))
            for c in analytics_response.conversations:
                analytics_conversations[c.conversation_id] = c
            query.paging['pageNumber'] = int(query.paging['pageNumber']) + 1
            analytics_response = analytics_api.post_analytics_conversations_details_query(query)

    count = len(analytics_conversations)
    print('Total conversations:', count)

    conversations_api = PureCloudPlatformClientV2.ConversationsApi()
    for i, key in enumerate(analytics_conversations):
        convo = analytics_conversations[key]
        print('GET conversation {0} of {1} (id {2})'.format(i + 1, count, convo.conversation_id))
        try:
            full_convo = conversations_api.get_conversation(convo.conversation_id)
            full_conversations.append(full_convo)

            ### FIXME - TEMP UNTIL PYTHON SDK CONVERSATION SERIALIZATION BUG FIX ###
            uri = '{0}/api/v2/conversations/{1}'.format(config['api_host'], convo.conversation_id)
            full_convo_json = json.loads(requests.get(uri, headers=auth_header).text)
            full_conversations_json.append(full_convo_json)
            #######################################################################################

        except ApiException as e:
            print('GET FAILED: conversation id: {0}'.format(convo.conversation_id))
            print(e)
        time.sleep(0.2)

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
    fieldnames = ['conversation_id', 'participant_id', 'participant_name', 'participant_purpose', 'participant_type',
                  'queue_id', 'queue_name', 'participant_ani', 'participant_dnis', 'user_id', 'user_name', 'user_email']
    fieldnames.extend(sorted(attributes_set))

    # Write curated Participant Data (each record = 1 conversation participant)
    with open('py-purecloud-participant-data.csv', 'w') as outfile:
        csvwriter = csv.DictWriter(outfile, delimiter=',', lineterminator='\n', fieldnames=fieldnames)
        csvwriter.writeheader()
        csvwriter.writerows(results)

    # Dump raw json of all conversations
    with open('py-full-conversation-data.json', 'w') as outfile:
        json.dump(full_conversations_json, outfile)

    # Flatten conversations and write as CSV
    flattened_convos = GetFlattenedConversations(full_conversations_json)

    field_set = set()
    for convo in flattened_convos:
        for field in convo:
            field_set.add(field)
    field_set_sorted = sorted(field_set)

    results = []
    for convo in flattened_convos:
        result = {}
        for field in field_set_sorted:
            result[field] = convo.get(field, '')
        results.append(result)

    with open('py-flattened-json-data.csv', 'w', encoding='utf8') as outfile:
        csvwriter = csv.DictWriter(outfile, delimiter=',', lineterminator='\n', fieldnames=field_set_sorted)
        csvwriter.writeheader()
        csvwriter.writerows(results)

except ApiException as exc:
    print('ApiException: {0}\n'.format(exc))

print("Exiting...")
