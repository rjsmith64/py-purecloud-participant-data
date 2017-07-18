import requests, socket, webbrowser, re, base64

def send_response(client_connection, responseStatus, responseBody):
    # Send response
    http_response = responseStatus + '\r\n\r\n' + responseBody
    print('[RESPONSE] ' + responseStatus + '\n')
    client_connection.sendall(http_response.encode('utf-8'))
    client_connection.close()

def get_implicit_grant_token(environment, client_id, redirect_uri, server_host, port):

    listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listen_socket.bind((server_host,port))
    listen_socket.listen(1)
    print('Serving HTTP on port %s ...' % port)

    webbrowser.open(redirect_uri)

    token = ''
    while token == '':
        client_connection, client_address = listen_socket.accept()
        request = client_connection.recv(1024)
        responseStatus = ''
        responseBody = ''

        # Parse out request verb and path
        request_str = request.decode('utf-8')
        matchObj = re.match(r'(GET) (\/.*) HTTP', request_str)

        if matchObj:
            verb = matchObj.group(1)
            path = matchObj.group(2)
            print('[REQUEST] ' + verb + ' ' + path)

        http_response = ''

        if path == '/' and verb == 'GET':
            # GET /
            with open('implicit.htm_', 'r') as htmlFile:
                responseStatus = 'HTTP/1.1 200 OK'
                responseBody = htmlFile.read() \
                        .replace('{{CONFIG_CLIENT_ID}}', client_id) \
                        .replace('{{CONFIG_ENVIRONMENT}}', environment) \
                        .replace('{{CONFIG_REDIRECT_URI}}', redirect_uri)
                send_response(client_connection, responseStatus, responseBody)

        elif path.startswith('/token/') and verb == 'GET':

            # GET /token/<token>
            token = path[7:]

            if token:
                responseStatus = 'HTTP/1.1 200 OK'
                responseBody = 'Authorized'
                send_response(client_connection, responseStatus, responseBody)
            else:
                responseStatus = 'HTTP/1.1 401 UNAUTHORIZED'
                responseBody = 'Authorization failed'
                send_response(client_connection, responseStatus, responseBody)

            listen_socket.close()
            return token

        else:
            # Invalid resource
            responseStatus = 'HTTP/1.1 404 NOT FOUND'
            responseBody = '404: NOT FOUND'
            send_response(client_connection, responseStatus, responseBody)

    # Should not reach
    return None

def get_client_credentials_token(environment, client_id, client_secret):

    login_url = 'https://login.' + environment + '/oauth/token'
    body_data = {'grant_type': 'client_credentials'}

    auth_string = 'Basic ' + base64.b64encode(bytes((client_id+':'+client_secret).encode('ascii'))).decode('ascii')

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': auth_string
    }
    res = requests.post(login_url, body_data, headers=headers)
    return res.json().get('access_token',None)


def get_oauth2_token(config):
    if config['oauth_type'] == 'implicit_grant':
        token = get_implicit_grant_token(
            config['environment'], config['client_id'], config['redirect_uri'], config['server_host'], config['port']
        )

    elif config['oauth_type'] == 'client_credentials':
        token = get_client_credentials_token(config['environment'], config['client_id'], config['client_secret'])

    else:
        raise ValueError('config oauth_type must be \'implicit_grant\' or \'client_credentials\'')

    return token
