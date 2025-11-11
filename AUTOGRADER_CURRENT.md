## Current Autograder Status (Phase 2)

- Latest run: 39 / 84  
- Logs: https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/API-Gateway-Execution-Logs_1q1x0d7k93$252Fprod/log-events/7887381aabb0afd610c0dc228d877154

### Issues
- 2025-11-11T03:45:50Z `GET /package/invalidId` → backend returned 404 but API Gateway only has a 200 method response, causing config error and 500 to client.
- 2025-11-09T23:08:46Z `POST /artifact/byRegEx` with regex `google-research-bert` → backend 404 “No artifact found under this regex.” (no matching artifacts ingested).
- 2025-11-09T23:08:47Z `POST /artifact/byRegEx` with regex `ece461rules` → backend 404 “No artifact found under this regex.” (no records matched pattern).
- 2025-11-09T23:08:48Z `POST /artifact/byRegEx` with regex `(a{1,99999}){1,99999}$` → backend 404 “No artifact found under this regex.” (stress regex returns empty set).
- 2025-11-09T23:09:04Z `GET /artifact/model/8228642810` → backend 404 “Artifact does not exist.” (ID not persisted).
- 2025-11-09T23:09:05Z `GET /artifact/model/8510140450` → backend 404 “Artifact does not exist.” (second lookup failure).
- 2025-11-09T23:09:08Z `GET /artifact/model/3023340011` → backend 404 “Artifact does not exist.” (ID missing from storage/S3).
- 2025-11-09T23:09:16Z `GET /artifact/model/8412004283` → backend 404 “Artifact does not exist.” (ID missing from storage/S3).
- 2025-11-09T23:09:09Z `GET /artifact/model/6514529035` → backend 404 “Artifact does not exist.” (additional missing model record).
- 2025-11-09T23:09:11Z `GET /artifact/model/5948785717` → backend 404 “Artifact does not exist.” (missing persisted entry).
- 2025-11-09T23:09:13Z `GET /artifact/model/1336304314` → backend 404 “Artifact does not exist.” (missing persisted entry).
- 2025-11-09T23:09:15Z `GET /artifact/model/5097499038` → backend 404 “Artifact does not exist.” (missing persisted entry).



RECENT LOG:
11/09/25 11:07:58 PM : INFO : Testing Directory: /app
11/09/25 11:07:58 PM : Test Start : Running Tests for: ECE461: Autograder Phase 2
11/09/25 11:07:58 PM : Test Start : Running Tests for: Setup and Reset Test Group
11/09/25 11:07:59 PM : Test Success : > System Health Test passed!
11/09/25 11:08:00 PM : Test Success : > System Tracks Test passed!
11/09/25 11:08:00 PM : Test Success : > Access Control Track is present!
11/09/25 11:08:01 PM : Test Success : > Login Successful!
11/09/25 11:08:02 PM : Test Success : > System Reset Test passed!
11/09/25 11:08:03 PM : Test Success : > No Artifacts present after reset!
11/09/25 11:08:03 PM : Test Result : Total score: 6 / 6 

11/09/25 11:08:03 PM : Test Start : Running Tests for: Upload Packages Test Group
11/09/25 11:08:11 PM : Test Success : > Ingest model 1 upload passed!
11/09/25 11:08:12 PM : Test Success : > Single Model Query Test passed!
11/09/25 11:08:12 PM : Test Success : > Ingest dataset 1 upload passed!
11/09/25 11:08:13 PM : Test Success : > Single Dataset Query Test passed!
11/09/25 11:08:14 PM : Test Success : > Ingest code 1 upload passed!
11/09/25 11:08:14 PM : Test Success : > Single Code Query Test passed!
11/09/25 11:08:16 PM : Test Success : > Ingest model 2 upload passed!
11/09/25 11:08:18 PM : Test Success : > Ingest model 3 upload passed!
11/09/25 11:08:20 PM : Test Success : > Ingest model 4 upload passed!
11/09/25 11:08:22 PM : Test Success : > Ingest model 5 upload passed!
11/09/25 11:08:24 PM : Test Success : > Ingest model 6 upload passed!
11/09/25 11:08:26 PM : Test Success : > Ingest model 7 upload passed!
11/09/25 11:08:30 PM : Test Success : > Ingest model 8 upload passed!
11/09/25 11:08:37 PM : Test Success : > Ingest model 9 upload passed!
11/09/25 11:08:38 PM : Test Success : > All Model Query Test passed!
11/09/25 11:08:38 PM : Test Success : > Ingest dataset 2 upload passed!
11/09/25 11:08:39 PM : Test Success : > Ingest dataset 3 upload passed!
11/09/25 11:08:40 PM : Test Success : > Ingest dataset 4 upload passed!
11/09/25 11:08:40 PM : Test Success : > Ingest dataset 5 upload passed!
11/09/25 11:08:41 PM : Test Success : > Ingest code 2 upload passed!
11/09/25 11:08:41 PM : Test Success : > Ingest code 3 upload passed!
11/09/25 11:08:42 PM : Test Success : > Ingest code 4 upload passed!
11/09/25 11:08:43 PM : Test Success : > Ingest code 5 upload passed!
11/09/25 11:08:43 PM : Test Success : > Ingest code 6 upload passed!
11/09/25 11:08:44 PM : Test Success : > Ingest code 7 upload passed!
11/09/25 11:08:44 PM : Test Success : > Ingest code 8 upload passed!
11/09/25 11:08:45 PM : Test Success : > All Artifacts Query Test passed!
11/09/25 11:08:45 PM : Test Result : Total score: 27 / 27 

11/09/25 11:08:45 PM : Test Start : Running Tests for: Regex Tests Group
11/09/25 11:08:46 PM : Test Fail : > Exact Match Name Regex Test failed!
11/09/25 11:08:46 PM : Test Success : > Extra Chars Name Regex Test passed!
11/09/25 11:08:47 PM : Test Success : > Random String Regex Test passed!
11/09/25 11:08:49 PM : Test Result : Total score: 2 / 6 (3 hidden)

11/09/25 11:08:49 PM : Test Start : Running Tests for: Artifact Read Test Group
11/09/25 11:08:49 PM : Test Fail : > Get Artifact By Name Test 0 failed!
11/09/25 11:08:50 PM : Test Success : > Get Artifact By Name Test 1 passed!
11/09/25 11:08:51 PM : Test Fail : > Get Artifact By Name Test 2 failed!
11/09/25 11:08:51 PM : Test Fail : > Get Artifact By Name Test 3 failed!
11/09/25 11:08:52 PM : Test Fail : > Get Artifact By Name Test 4 failed!
11/09/25 11:08:53 PM : Test Fail : > Get Artifact By Name Test 5 failed!
11/09/25 11:08:53 PM : Test Fail : > Get Artifact By Name Test 6 failed!
11/09/25 11:08:54 PM : Test Success : > Get Artifact By Name Test 7 passed!
11/09/25 11:08:54 PM : Test Fail : > Get Artifact By Name Test 8 failed!
11/09/25 11:08:55 PM : Test Fail : > Get Artifact By Name Test 9 failed!
11/09/25 11:08:56 PM : Test Fail : > Get Artifact By Name Test 10 failed!
11/09/25 11:08:56 PM : Test Success : > Get Artifact By Name Test 11 passed!
11/09/25 11:08:57 PM : Test Fail : > Get Artifact By Name Test 12 failed!
11/09/25 11:08:58 PM : Test Fail : > Get Artifact By Name Test 13 failed!
11/09/25 11:08:58 PM : Test Fail : > Get Artifact By Name Test 14 failed!
11/09/25 11:08:59 PM : Test Fail : > Get Artifact By Name Test 15 failed!
11/09/25 11:08:59 PM : Test Success : > Get Artifact By Name Test 16 passed!
11/09/25 11:09:00 PM : Test Success : > Get Artifact By Name Test 17 passed!
11/09/25 11:09:01 PM : Test Fail : > Get Artifact By Name Test 18 failed!
11/09/25 11:09:01 PM : Test Fail : > Get Artifact By Name Test 19 failed!
11/09/25 11:09:02 PM : Test Fail : > Get Artifact By Name Test 20 failed!
11/09/25 11:09:03 PM : Test Fail : > Get Artifact By Name Test 21 failed!
11/09/25 11:09:03 PM : Test Fail : > Get Artifact By ID Test 0 failed!
11/09/25 11:09:04 PM : Test Success : > Get Artifact By ID Test 1 passed!
11/09/25 11:09:04 PM : Test Fail : > Get Artifact By ID Test 2 failed!
11/09/25 11:09:05 PM : Test Fail : > Get Artifact By ID Test 3 failed!
11/09/25 11:09:06 PM : Test Fail : > Get Artifact By ID Test 4 failed!
11/09/25 11:09:06 PM : Test Fail : > Get Artifact By ID Test 5 failed!
11/09/25 11:09:07 PM : Test Fail : > Get Artifact By ID Test 6 failed!
11/09/25 11:09:08 PM : Test Fail : > Get Artifact By ID Test 7 failed!
11/09/25 11:09:08 PM : Test Fail : > Get Artifact By ID Test 8 failed!
11/09/25 11:09:09 PM : Test Fail : > Get Artifact By ID Test 9 failed!
11/09/25 11:09:09 PM : Test Fail : > Get Artifact By ID Test 10 failed!
11/09/25 11:09:10 PM : Test Success : > Get Artifact By ID Test 11 passed!
11/09/25 11:09:11 PM : Test Fail : > Get Artifact By ID Test 12 failed!
11/09/25 11:09:11 PM : Test Fail : > Get Artifact By ID Test 13 failed!
11/09/25 11:09:12 PM : Test Fail : > Get Artifact By ID Test 14 failed!
11/09/25 11:09:13 PM : Test Fail : > Get Artifact By ID Test 15 failed!
11/09/25 11:09:13 PM : Test Success : > Get Artifact By ID Test 16 passed!
11/09/25 11:09:14 PM : Test Success : > Get Artifact By ID Test 17 passed!
11/09/25 11:09:15 PM : Test Fail : > Get Artifact By ID Test 18 failed!
11/09/25 11:09:15 PM : Test Fail : > Get Artifact By ID Test 19 failed!
11/09/25 11:09:16 PM : Test Fail : > Get Artifact By ID Test 20 failed!
11/09/25 11:09:16 PM : Test Fail : > Get Artifact By ID Test 21 failed!
11/09/25 11:09:17 PM : Test Fail : > Invalid Package Read Test failed!
11/09/25 11:09:17 PM : Test Result : Total score: 9 / 45 

11/09/25 11:09:17 PM : Test Result : Total score: 44 / 84 

Ethan's Analysis of errors at 44/84 state
A majoirty of our errors come from trying to find artifact by a parameter
Starting with name, when we ingest a model via POST /Artificat/model, it assigns it a random numeric value, but never a mapping

Essentially, we are genearting a random ID and never saving the metadata under that key. 

Soultion: Persist artifact metadata, keyed by the returned metadata.id

How are we currenlty storign metadata? src/index.py has in-mem dict. There is no metadata that is persisted. 

The easiest way is to take our in-mem metadata and insert an entry in _artifcat_storage keyed by gen ID with artifacts name/type/url/version

Endpoints should consult a map first