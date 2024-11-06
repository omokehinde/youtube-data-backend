### Welcome to YouTube Data procesing. 
YouTube Data processing allows you to Fetch details of a specific YouTube video using the YouTube Data API. It allows you to Load comments for the video, fetching all available comments (paginated if necessary)

To install and run this application locally: 
1. run `git pull https://github.com/omokehinde/youtube-data-backend.git`
2. run `cd  youtube-data-backen`
3. run `python3 -m venv .venv` if you are linux or mac, `py -m venv .venv` if you are on windows. Run either of these command depending on your OS only if you will like to use a virual enviroment. If you don't like to use a virtual enviroment you can skip to step 5
4. run `source .venv/bin/activate` if you are on linux or mac, `source .venv/Scripts/activate` if you are on windows
5. run `pip install -r requirements.txt`
6. create a .env and put the YOUTUBE_API_KEY=your_youtube_api_key
7. run `pip install -e .`
8. run `python -m src.youtube_api.app`

To run Test:
1. run `pip install -e ".[dev]"`
2. run `pytest` to run the tests
3. run `pytest --cov=youtube_api --cov-report=term-missing` to run test with coverage

If you have any questions you can reach out to me via email or whatsapp. Happy codding. 

