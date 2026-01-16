T001: Build Macroeconomic News Release Analyst Agent

	Features
		Generates daily sentiment breifings
		Generates sentiment breifings whenever high impact indicator's data releases
		Can send out sentiment breifings via email, or webhook
		Filter out low impact noise or emotional manipulation
		
	Memory:
		Saves sentiment breifings
			Uses past breifings if needed
		Doesnt spam out same story, if nothing new has happened
			I dont want messages in discord every 30mins
		Has a schedule of upcoming high impact releases
	Data Sources:
		MCP Endpoints
		APIs
		RSS Feeds
		Web Scraping
