import anthropic

client = anthropic.Anthropic(
    api_key="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"
)

response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=200,
    messages=[
        {"role": "user", "content": "Explain microservices"}
    ]
)

print(response.content)