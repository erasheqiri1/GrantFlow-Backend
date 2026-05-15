from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
middleware
from app.middleware.auth import AuthMiddleware
from app.middleware.tenant import TenantMiddleware

app = FastAPI(
    title="GrantFlow API",
    description="Platformë SaaS për menaxhimin e granteve",
    version="1.0.0",
)

#cors


app = FastAPI(
    title="GrantFlow API",
    version="1.0.0"
)

main
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

middleware
# middleware

app.add_middleware(TenantMiddleware)
app.add_middleware(AuthMiddleware)

#testim

@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "app": "GrantFlow API"}


@app.get('/')
def root():

    return {'message': 'GrantFlow API'}
main
