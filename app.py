from sanic import Sanic, response
import asyncio
import concurrent.futures
import requests
import tweepy
import os

twitter_auth = tweepy.OAuthHandler('<TWITTER_CONSUMER_KEY>', '<TWITTER_CONSUMER_SECRET>')
twitter_auth.set_access_token('<TWITTER_ACCESS_KEY>', '<TWITTER_ACCESS_SECRET>')
twitter_api = tweepy.API(twitter_auth)

app = Sanic()

NO_RESULTS_JSON = {"error": -1, "message": "No Results"}
RESULT_JSON = lambda x: {"text": x}
TIMEOUT_JSON = {"error": -1, "message": "execution timed out"}

def get_google_result(q):
    res = requests.get("https://www.googleapis.com/customsearch/v1?key=<GOOGLE_API_SECRET>&cx=011634103780127050272%3A8dm3slkgwwg&q={}&start=1&num=1".format(q)).json()
    if res['items']:
        return RESULT_JSON(res['items'][0]['snippet'])
    return NO_RESULTS_JSON

def get_duckduckgo_result(q):
    res = requests.get("http://api.duckduckgo.com/?q={}&format=json".format(q)).json()
    if res['RelatedTopics']:
        return RESULT_JSON(res['RelatedTopics'][0]['Text'])
    return NO_RESULTS_JSON

def get_twitter_result(q):
    res = twitter_api.search(q, count=1)
    if len(res):
        return RESULT_JSON(res.pop().text)
    return NO_RESULTS_JSON

@app.route("/")
async def home(request):
    q = request.args.get('q')
    res = {"query": q, "google": TIMEOUT_JSON, "twitter": TIMEOUT_JSON, "duckduckgo": TIMEOUT_JSON}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_to_result = {
            executor.submit(engine['fun'], q): engine['engine'] for engine in [{
                "engine": "google",
                "fun": get_google_result
                }, {
                "engine": "duckduckgo",
                "fun": get_duckduckgo_result
                }, {
                "engine": "twitter",
                "fun": get_twitter_result
                }]
        }
        try:
            # As and when results are available push them into res[Response]. Timeout set to 1
            for future in concurrent.futures.as_completed(future_to_result, 1):
                engine = future_to_result[future]
                try:
                    data = future.result()
                except Exception as exc:
                    res[engine] = {"error": -1, "message": "Something went wrong!"}
                else:
                    res[engine] = data
        except Exception as err:
            # In case of timeout timed out calls will continue to have the initial TIMEOUT_JSON. Ones that succeeded will have actual result.
            pass
    return response.json(res)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=os.environ.get('PORT', 5000))
