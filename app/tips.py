class TipFormatter:
    def tip_metadata(metadata: dict):
        search_text = f"🔍 Searched \"{metadata['question']}\""

        start_date = metadata['date_range']['start_date']
        end_date = metadata['date_range']['end_date']

        date_text = ""
        if start_date and end_date:
            date_text = f"⏳ From {start_date} to {end_date}."
        elif start_date:
            date_text = f"⏳ After {start_date}."
        elif end_date:
            date_text = f"⏳ Until {end_date}"

        author_text = ""
        if len(metadata["authors"]) == 1:
            author_text = f"🖊️ Written by {metadata['authors'][0]}"
        elif len(metadata['authors']) > 1:
            author_text = f"🖊️ Written by {', '.join(metadata['authors'][:-1])}, and {metadata['authors'][-1]}"

        text_blocks = filter(lambda x: len(x) > 0, [search_text, date_text, author_text])
        return "\n".join(text_blocks)
    
    def tip_search(sources: list):
        return f"🔍 Retrieved {len(sources)} articles."

        