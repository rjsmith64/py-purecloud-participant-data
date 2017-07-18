Exports Participant attributes ("Participant Data") and other analytics to CSV for conversations found by Conversation Details Query.

Release Notes / Updates:
2017-07-18:
- Added export of full conversation data (raw json and flattened csv)
- queries.json - can now add multiple conversation detail queries; used when desired interval exceeds maximum and query must be broken into sub-queries. 

How-to:

Edit queries.json to specify array of Conversation Details Queries (conversations included in multiple queries will be de-duplicated).

Edit configuration.json to specify:
- Regional environment settings
- Oauth options
- Participant purpose export settings

Running executable-only:

Download and unzip Windows binary from build/ folder. Run 'py-purecloud-participant-data.exe' after configuring configuration.json and queries.json.

Required PureCloud permissions:
- Analytics > conversationDetail > View
- Directory > User > View
- Routing > Queue > View
- Conversation > Communication > View
