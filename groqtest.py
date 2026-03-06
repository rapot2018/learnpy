from groq import Groq

client = Groq(api_key="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")

chat = client.chat.completions.create(
    messages=[{"role":"user","content":"Java Jobs Remote in USA newly posted"}],
    model="llama-3.1-8b-instant"
)

print(chat.choices[0].message.content)