import sys
import json
from connectors.postgresql import PostgresqlConnector
from flask import Flask,request
app = Flask(__name__)

serverConfig = None
dbmsConfig = None
pools = {}
dbms = None

# give this dbms setup a name
def getConnectionName(dbmsConfig):
  name = dbmsConfig["dbmsName"]+":"+dbmsConfig["dbname"]
  if "port" in dbmsConfig:
    name += " | "+str(dbmsConfig["port"])
  return name

# handle SQL query requests for vega dataflow
@app.route("/query", methods = ["POST","GET"])
def executeQuery():
  client = None
  query = None
  try:
    if request.method == "POST":
      query = request.form["query"]
    else:
      query = request.args.get("query")
    if query is None:
      raise "request body must define query property"
    results = dbms.executeQuery(query)
    return json.dumps(results)
  except Exception as err:
    #print(err)
    #return str(err)
    raise err

# handle requests to create and populate a table in the DBMS
@app.route("/createSql", methods = ["POST"])
def createSqlTable():
  client = None
  try:
    #params = request.get_json()
    #print(json.dumps(params))
    data = request.form["data"]
    name = request.form["name"]
    if not data:
      raise "request body must define data property";
    if not name:
      raise "request body must define name property";

    # Check if table exists yet
    exists = False
    existsQueryStr = "select exists(select 1 from information_schema.tables where table_name=" + "'" + name.lower() + "');"
      
    response = dbms.executeQuery(existsQueryStr)
    print(json.dumps(response))
    print("testing")
    if response[0]["exists"]:
      exists = True
      print("table %s already exists" % (name))
    else:
      exists = False
      print("table %s does not exist" % (name))

    data = json.loads(data)
    schema = dbms.schemaFor(data[0])

    # Create table if it doesn't exist yet
    if not exists:
      print("creating table %s" % (name))
      print("built postgres schema: %s" % (json.dumps(schema)))
      createTableQueryStr = dbms.createTableQueryStrFor(name, schema)
      print("running create query: '%s'" % (createTableQueryStr));
      dbms.executeQueryNoResults(createTableQueryStr)

      # Insert values
      # Build attribute list string e.g. (attr1, attr2, attr3)
      attrNames = schema.keys()

      insertStatements = []
      for row in data:
        print(row)
        st = "INSERT INTO " + name + " VALUES ( "
        for a in attrNames:
          out = row[a]
          print(row,a,out)
          if type(out) == str:
            out = row[a]
            out = out.replace("'", "''")
            out = out.replace("\"", "'" if serverConfig["keepquotes"] else "")
            if out[0] != "'" or out[-1] != "'": # no quotes
              out = "'" + out + "'"
          if out is None:
            out = "null"
          st += "{0},".format(out)
        st = st[:-1] + " );"
        print(st)
        print(schema)
        insertStatements.append(st)
      print("running insert queries for %s" % (name))
      dbms.executeQueriesNoResults(insertStatements)
      print("insert queries complete")
    return "success"
  except Exception as err:
    #print(err)
    #return str(err)
    raise err

if __name__ == "__main__":
  scf = "server.config.json"
  dcf = "dbms.config.json"
  if len(sys.argv) == 3:
    scf = sys.argv[1]
    dcf = sys.argv[2]
  with open(scf,"r") as f:
    serverConfig = json.load(f)
  with open(dcf,"r") as f:
    dbmsConfig = json.load(f)

  dbms = PostgresqlConnector(dbmsConfig,getConnectionName(dbmsConfig))
  app.run(debug=True,port=serverConfig["port"])