#!/usr/bin/env python2.7

"""
Columbia W4111 Intro to databases

David Chen (dhc2129)
Lusa Zhan (lz2371)
"""

import os
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, Response

tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)

DATABASEURI = "postgresql://dhc2129:199@w4111db1.cloudapp.net:5432/proj1part2"

#
# This line creates a database engine that knows how to connect to the URI above
#
engine = create_engine(DATABASEURI)

@app.before_request
def before_request():
  """
  This function is run at the beginning of every web request 
  (every time you enter an address in the web browser).
  We use it to setup a database connection that can be used throughout the request

  The variable g is globally accessible
  """
  try:
    g.conn = engine.connect()
  except:
    print "uh oh, problem connecting to database"
    import traceback; traceback.print_exc()
    g.conn = None

@app.teardown_request
def teardown_request(exception):
  """
  At the end of the web request, this makes sure to close the database connection.
  If you don't the database could run out of memory!
  """
  try:
    g.conn.close()
  except Exception as e:
    pass


#
# @app.route is a decorator around index() that means:
#   run index() whenever the user tries to access the "/" path using a POST or GET request
#
# If you wanted the user to go to e.g., localhost:8111/foobar/ with POST or GET then you could use
#
#       @app.route("/foobar/", methods=["POST", "GET"])
#
# PROTIP: (the trailing / in the path is important)
# 
# see for routing: http://flask.pocoo.org/docs/0.10/quickstart/#routing
# see for decorators: http://simeonfranklin.com/blog/2012/jul/1/python-decorators-in-12-steps/
# 

@app.route('/', methods=["POST", "GET"])
def index():
  """
  request is a special object that Flask provides to access web request information:

  request.method:   "GET" or "POST"
  request.form:     if the browser submitted a form, this contains the data in the form
  request.args:     dictionary of URL arguments e.g., {a:1, b:2} for http://localhost?a=1&b=2

  See its API: http://flask.pocoo.org/docs/0.10/api/#incoming-request-data
  """

  print request.args

  searchVal = request.args.get('searchVal')
  if searchVal is not None:
    sql = """
      SELECT * 
      FROM recipes r 
      WHERE r.name 
      LIKE '%%'||%s||'%%'
      """
    print sql % searchVal
    cursor = g.conn.execute(sql, (searchVal))
  else:
    cursor = g.conn.execute("SELECT * FROM recipes")

  recipes = []
  for result in cursor:
    recipes.append(result['name'])  # can also be accessed using result[0]
  cursor.close()

  #
  # Flask uses Jinja templates, which is an extension to HTML where you can
  # pass data to a template and dynamically generate HTML based on the data
  # (you can think of it as simple PHP)
  # documentation: https://realpython.com/blog/python/primer-on-jinja-templating/
  #
  # You can see an example template in templates/index.html
  #
  # context are the variables that are passed to the template.
  # for example, "data" key in the context variable defined below will be 
  # accessible as a variable in index.html:
  #

  context = dict( data = recipes )


  #
  # render_template looks in the templates/ folder for files.
  # for example, the below file reads template/index.html
  #
  return render_template("index.html", **context)



#
# Recipe Page Template
#
@app.route('/recipePage/<r_id>', methods = ["POST", "GET"])
def recipePage(r_id):
  result = []
  #recipe info
  cursor = g.conn.execute("SELECT * FROM recipes r WHERE r.id = %s", (r_id))
  if cursor is None:
    return render_template("404.html")

  result = cursor.fetchone()
  r = {'name':result['name'],
    'instr': result['instructions'], 
    'time':result['preparation_time'], 
    'user':result['user_posted']}
  if r.get('time') is None:
    r['time']='unknown'
  if r.get('user') is None:
    r['user']='Admin'
  
  #cuisine
  sql_cuisine = """SELECT C.name
        FROM cuisines C, recipe_cuisines RC
        WHERE RC.cuisine_id = C.id AND RC.recipe_id = %s"""
  cursor = g.conn.execute(sql_cuisine, r_id)
  result = cursor.fetchone();
  r['cuisine'] = result[0];
  if r.get('cuisine') is None:
    r['cuisine'] = "N/A"
  
  #ingredients
  ingred = []
  price = 0
  sql_ingred = """SELECT I.name, RI.quantity, I.measurement_type, I.price
        FROM ingredients I, recipe_ingredients RI
        WHERE RI.ingredient_id = I.id AND RI.recipe_id = %s;"""
  cursor = g.conn.execute(sql_ingred, (r_id))
  result = []
  for result in cursor:
    if result is not None:
      price += result[1]*result[3]
      ingred.append(str(result[1])+" "+str(result[2])+" "+str(result[0]))
  if ingred == [] :
    ingred.append("N/A")
  r['ingred'] = ingred
  
  #price of ingredients:
  r['price'] = price
  
  #rating
  sql_rating = """SELECT AVG(RV.rating)
        FROM recipes R INNER JOIN user_reviews RV 
        ON R.id = RV.recipe_id WHERE R.id IN 
        (SELECT user_reviews.recipe_id 
	      FROM user_reviews
        WHERE R.id=%s) 
	      GROUP BY id;"""
  
  cursor = g.conn.execute(sql_rating, (r_id))
  avg = cursor.fetchone()
  if avg is None:
    r['rating'] = 0
  else:
    r['rating'] = avg[0]
    
    #comments
    comments = []
    sql_comments = """SELECT U.username, UR.rating, UR.description
          FROM users U, user_reviews UR
          WHERE U.id = UR.user_id AND UR.recipe_id = %s"""
    cursor = g.conn.execute(sql_comments, (r_id))
    result = []
    for result in cursor:
      if result is not None:
        if result[2] is not None:
          comments.append(result)
          
    r['comments'] = comments 
  
  #close and return
  cursor.close()
  return render_template("recipePage.html", **r)
    

if __name__ == "__main__":
  import click

  @click.command()
  @click.option('--debug', is_flag=True)
  @click.option('--threaded', is_flag=True)
  @click.argument('HOST', default='0.0.0.0')
  @click.argument('PORT', default=8111, type=int)
  def run(debug, threaded, host, port):
    """
    This function handles command line parameters.
    Run the server using

        python server.py

    Show the help text using

        python server.py --help

    """

    HOST, PORT = host, port
    print "running on %s:%d" % (HOST, PORT)
    app.run(host=HOST, port=PORT, debug=debug, threaded=threaded)


  run()
