from WebGlacier import app,db
db.create_all()
app.run(app.config.get('APP_HOST'))
