def summarize_text(text: str) -> list[str]:
    text = text.strip()

    if not text:
        return []

    sentences = []
    for part in text.replace("!", ".").replace("?", ".").split("."):
        part = part.strip()
        if part:
            sentences.append(part)

    if not sentences:
        return [text]

    result = []
    for sentence in sentences[:3]:
        if sentence.endswith("."):
            result.append(sentence)
        else:
            result.append(sentence + ".")

    return result