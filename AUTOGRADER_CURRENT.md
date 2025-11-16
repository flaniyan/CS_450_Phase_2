## Current Autograder Status (Phase 2)

- Latest run: 82/101  
- Logs: https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/API-Gateway-Execution-Logs_1q1x0d7k93$252Fprod/log-events/7887381aabb0afd610c0dc228d877154

### Issues
- Extra Chars Handling for ReGex endpoint
- Some of the GET calls still aren't working



RECENT LOG:
11/16/25 06:11:51 PM : INFO : Testing Directory: /app
11/16/25 06:11:51 PM : Test Start : Running Tests for: ECE461: Autograder Phase 2
11/16/25 06:11:51 PM : Test Start : Running Tests for: Setup and Reset Test Group
11/16/25 06:11:52 PM : Test Success : > System Health Test passed!
11/16/25 06:11:53 PM : Test Success : > System Tracks Test passed!
11/16/25 06:11:53 PM : Test Success : > Access Control Track is present!
11/16/25 06:11:54 PM : Test Success : > Login Successful!
11/16/25 06:11:55 PM : Test Success : > System Reset Test passed!
11/16/25 06:11:56 PM : Test Success : > No Artifacts present after reset!
11/16/25 06:11:56 PM : Test Result : Total score: 6 / 6 

11/16/25 06:11:56 PM : Test Start : Running Tests for: Upload Packages Test Group
11/16/25 06:11:58 PM : Test Success : > Ingest model 1 upload passed!
11/16/25 06:11:59 PM : Test Success : > Single Model Query Test passed!
11/16/25 06:12:00 PM : Test Success : > Ingest dataset 1 upload passed!
11/16/25 06:12:00 PM : Test Success : > Single Dataset Query Test passed!
11/16/25 06:12:01 PM : Test Success : > Ingest code 1 upload passed!
11/16/25 06:12:02 PM : Test Success : > Single Code Query Test passed!
11/16/25 06:12:03 PM : Test Success : > Ingest model 2 upload passed!
11/16/25 06:12:05 PM : Test Success : > Ingest model 3 upload passed!
11/16/25 06:12:06 PM : Test Success : > Ingest model 4 upload passed!
11/16/25 06:12:08 PM : Test Success : > Ingest model 5 upload passed!
11/16/25 06:12:09 PM : Test Success : > Ingest model 6 upload passed!
11/16/25 06:12:11 PM : Test Success : > Ingest model 7 upload passed!
11/16/25 06:12:12 PM : Test Success : > Ingest model 8 upload passed!
11/16/25 06:12:14 PM : Test Success : > Ingest model 9 upload passed!
11/16/25 06:12:16 PM : Test Success : > Ingest model 10 upload passed!
11/16/25 06:12:17 PM : Test Success : > All Model Query Test passed!
11/16/25 06:12:17 PM : Test Success : > Ingest dataset 2 upload passed!
11/16/25 06:12:18 PM : Test Success : > Ingest dataset 3 upload passed!
11/16/25 06:12:19 PM : Test Success : > Ingest dataset 4 upload passed!
11/16/25 06:12:19 PM : Test Success : > Ingest dataset 5 upload passed!
11/16/25 06:12:20 PM : Test Success : > Ingest code 2 upload passed!
11/16/25 06:12:20 PM : Test Success : > Ingest code 3 upload passed!
11/16/25 06:12:21 PM : Test Success : > Ingest code 4 upload passed!
11/16/25 06:12:22 PM : Test Success : > Ingest code 5 upload passed!
11/16/25 06:12:22 PM : Test Success : > Ingest code 6 upload passed!
11/16/25 06:12:23 PM : Test Success : > Ingest code 7 upload passed!
11/16/25 06:12:24 PM : Test Success : > Ingest code 8 upload passed!
11/16/25 06:12:24 PM : Test Success : > Ingest code 9 upload passed!
11/16/25 06:12:25 PM : Test Success : > All Artifacts Query Test passed!
11/16/25 06:12:25 PM : Test Result : Total score: 29 / 29 

11/16/25 06:12:25 PM : Test Start : Running Tests for: Regex Tests Group
11/16/25 06:12:27 PM : Test Success : > Exact Match Name Regex Test passed!
11/16/25 06:12:28 PM : Test Fail : > Extra Chars Name Regex Test failed!
11/16/25 06:12:30 PM : Test Success : > Random String Regex Test passed!
11/16/25 06:12:32 PM : Test Result : Total score: 5 / 6 (3 hidden)

11/16/25 06:12:32 PM : Test Start : Running Tests for: Artifact Read Test Group
11/16/25 06:12:33 PM : Test Success : > Get Artifact By Name Test 0 passed!
11/16/25 06:12:33 PM : Test Success : > Get Artifact By Name Test 1 passed!
11/16/25 06:12:34 PM : Test Fail : > Get Artifact By Name Test 2 failed!
11/16/25 06:12:35 PM : Test Fail : > Get Artifact By Name Test 3 failed!
11/16/25 06:12:35 PM : Test Success : > Get Artifact By Name Test 4 passed!
11/16/25 06:12:36 PM : Test Success : > Get Artifact By Name Test 5 passed!
11/16/25 06:12:36 PM : Test Success : > Get Artifact By Name Test 6 passed!
11/16/25 06:12:37 PM : Test Success : > Get Artifact By Name Test 7 passed!
11/16/25 06:12:38 PM : Test Success : > Get Artifact By Name Test 8 passed!
11/16/25 06:12:38 PM : Test Success : > Get Artifact By Name Test 9 passed!
11/16/25 06:12:39 PM : Test Fail : > Get Artifact By Name Test 10 failed!
11/16/25 06:12:40 PM : Test Success : > Get Artifact By Name Test 11 passed!
11/16/25 06:12:40 PM : Test Fail : > Get Artifact By Name Test 12 failed!
11/16/25 06:12:41 PM : Test Success : > Get Artifact By Name Test 13 passed!
11/16/25 06:12:42 PM : Test Fail : > Get Artifact By Name Test 14 failed!
11/16/25 06:12:42 PM : Test Fail : > Get Artifact By Name Test 15 failed!
11/16/25 06:12:43 PM : Test Success : > Get Artifact By Name Test 16 passed!
11/16/25 06:12:43 PM : Test Success : > Get Artifact By Name Test 17 passed!
11/16/25 06:12:44 PM : Test Fail : > Get Artifact By Name Test 18 failed!
11/16/25 06:12:45 PM : Test Success : > Get Artifact By Name Test 19 passed!
11/16/25 06:12:45 PM : Test Success : > Get Artifact By Name Test 20 passed!
11/16/25 06:12:46 PM : Test Fail : > Get Artifact By Name Test 21 failed!
11/16/25 06:12:47 PM : Test Success : > Get Artifact By Name Test 22 passed!
11/16/25 06:12:47 PM : Test Fail : > Get Artifact By Name Test 23 failed!
11/16/25 06:12:48 PM : Test Success : > Get Artifact By ID Test 0 passed!
11/16/25 06:12:49 PM : Test Success : > Get Artifact By ID Test 1 passed!
11/16/25 06:12:49 PM : Test Fail : > Get Artifact By ID Test 2 failed!
11/16/25 06:12:50 PM : Test Fail : > Get Artifact By ID Test 3 failed!
11/16/25 06:12:50 PM : Test Success : > Get Artifact By ID Test 4 passed!
11/16/25 06:12:51 PM : Test Success : > Get Artifact By ID Test 5 passed!
11/16/25 06:12:52 PM : Test Success : > Get Artifact By ID Test 6 passed!
11/16/25 06:12:52 PM : Test Success : > Get Artifact By ID Test 7 passed!
11/16/25 06:12:53 PM : Test Success : > Get Artifact By ID Test 8 passed!
11/16/25 06:12:53 PM : Test Success : > Get Artifact By ID Test 9 passed!
11/16/25 06:12:54 PM : Test Fail : > Get Artifact By ID Test 10 failed!
11/16/25 06:12:55 PM : Test Success : > Get Artifact By ID Test 11 passed!
11/16/25 06:12:55 PM : Test Fail : > Get Artifact By ID Test 12 failed!
11/16/25 06:12:56 PM : Test Success : > Get Artifact By ID Test 13 passed!
11/16/25 06:12:57 PM : Test Fail : > Get Artifact By ID Test 14 failed!
11/16/25 06:12:57 PM : Test Fail : > Get Artifact By ID Test 15 failed!
11/16/25 06:12:58 PM : Test Success : > Get Artifact By ID Test 16 passed!
11/16/25 06:12:58 PM : Test Success : > Get Artifact By ID Test 17 passed!
11/16/25 06:12:59 PM : Test Fail : > Get Artifact By ID Test 18 failed!
11/16/25 06:13:00 PM : Test Success : > Get Artifact By ID Test 19 passed!
11/16/25 06:13:00 PM : Test Success : > Get Artifact By ID Test 20 passed!
11/16/25 06:13:01 PM : Test Fail : > Get Artifact By ID Test 21 failed!
11/16/25 06:13:02 PM : Test Success : > Get Artifact By ID Test 22 passed!
11/16/25 06:13:02 PM : Test Fail : > Get Artifact By ID Test 23 failed!
11/16/25 06:13:05 PM : Test Success : > Invalid Artifact Read Test passed!
11/16/25 06:13:05 PM : Test Result : Total score: 31 / 49 

11/16/25 06:13:05 PM : Test Start : Running Tests for: Rate models concurrently Test Group
11/16/25 06:13:05 PM : Test Success : > Get Artifact Rate Test passed for Artifact 0!
11/16/25 06:13:05 PM : Test Success : > Get Artifact Rate Test passed for Artifact 3!
11/16/25 06:13:05 PM : Test Success : > Get Artifact Rate Test passed for Artifact 6!
11/16/25 06:13:05 PM : Test Success : > Get Artifact Rate Test passed for Artifact 1!
11/16/25 06:13:05 PM : Test Success : > Get Artifact Rate Test passed for Artifact 4!
11/16/25 06:13:05 PM : Test Success : > Get Artifact Rate Test passed for Artifact 5!
11/16/25 06:13:05 PM : Test Success : > Get Artifact Rate Test passed for Artifact 7!
11/16/25 06:13:05 PM : Test Success : > Get Artifact Rate Test passed for Artifact 9!
11/16/25 06:13:05 PM : Test Success : > Get Artifact Rate Test passed for Artifact 8!
11/16/25 06:13:05 PM : Test Success : > Get Artifact Rate Test passed for Artifact 2!
11/16/25 06:13:07 PM : Test Result : Total score: 11 / 11 (1 hidden)

11/16/25 06:13:07 PM : Test Result : Total score: 82 / 101 


Ethan's Analysis of errors at 44/84 state
A majoirty of our errors come from trying to find artifact by a parameter
Starting with name, when we ingest a model via POST /Artificat/model, it assigns it a random numeric value, but never a mapping

Essentially, we are genearting a random ID and never saving the metadata under that key. 

Soultion: Persist artifact metadata, keyed by the returned metadata.id

How are we currenlty storign metadata? src/index.py has in-mem dict. There is no metadata that is persisted. 

The easiest way is to take our in-mem metadata and insert an entry in _artifcat_storage keyed by gen ID with artifacts name/type/url/version

Endpoints should consult a map first