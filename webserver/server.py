#!/usr/bin/env python2.7

"""
Columbia W4111 Intro to databases

David Chen (dhc2129)
Lusa Zhan (lz2371)
"""

import os
from operator import itemgetter
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, Response, session, flash, url_for

tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)
app.secret_key = 'doesnt really matter what this is'

DATABASEURI = "postgresql://dhc2129:199@w4111db1.cloudapp.net:5432/proj1part2"

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

@app.route('/', methods=["POST", "GET"])
def index():

  print request.args

  searchVal = request.args.get('searchVal')
  if searchVal is not None:
    sql = """
      SELECT R.id, R.name, R.preparation_time, AVG(RV.rating), C.name, FT.name
      FROM recipes R LEFT OUTER JOIN user_reviews RV ON (R.id = RV.recipe_id) 
        LEFT OUTER JOIN recipe_cuisines RC ON (R.id = RC.recipe_id) 
          INNER JOIN cuisines C ON (C.id = RC.cuisine_id)
        LEFT OUTER JOIN recipe_food_type RT ON (R.id = RT.recipe_id) 
          INNER JOIN food_types FT ON (FT.id = RT.type_id) 
      WHERE R.name LIKE '%%'||%s||'%%' OR C.name LIKE '%%'||%s||'%%' OR FT.name LIKE '%%'||%s||'%%'
      GROUP BY R.id, C.name, FT.name; 
      """
    # print sql % searchVal
    cursor = g.conn.execute(sql, (searchVal,searchVal,searchVal))
  else:
    sql = """
      SELECT R.id, R.name, R.preparation_time, AVG(RV.rating), C.name, FT.name
      FROM recipes R LEFT OUTER JOIN user_reviews RV ON (R.id = RV.recipe_id) 
        LEFT OUTER JOIN recipe_cuisines RC ON (R.id = RC.recipe_id) 
          INNER JOIN cuisines C ON (C.id = RC.cuisine_id)
        LEFT OUTER JOIN recipe_food_type RT ON (R.id = RT.recipe_id) 
          INNER JOIN food_types FT ON (FT.id = RT.type_id) 
      GROUP BY R.id, C.name, FT.name;
    """
    cursor = g.conn.execute(sql)

  recipes = []
  for result in cursor:
    preparation_time = result['preparation_time']
    if preparation_time is None:
      preparation_time = 'unknown'
    rating = result[3]
    if rating is None:
      rating = 0;
    cuisine = result[4]
    foodType = result[5]
    recipe = {
      'id': result['id'],
      'name': result[1],
      'preparation_time': preparation_time,
      'rating': rating,
      'cuisine': [cuisine],
      'type': [foodType]
    }
    recipes.append(recipe)
  cursor.close()

  recipes = sorted(recipes, key=itemgetter('id'))
  i=0;
  while i < len(recipes)-1:
    if recipes[i]['id'] == recipes[i+1]['id']:
      if recipes[i]['cuisine'][0] != recipes[i+1]['cuisine'][0]:
        recipes[i]['cuisine'].append(recipes[i+1]['cuisine'][0])
      if recipes[i]['type'][0] != recipes[i+1]['type'][0]:
        recipes[i]['type'].append(recipes[i+1]['type'][0])
      recipes.pop(i+1) 
    i+=1  

  context = dict( data = recipes )

  return render_template("index.html", **context)


#login page
@app.route('/login', methods = ['POST'])
def login():
  username = request.form['username']
  sql = """
  SELECT * from users U
  WHERE U.username = %s
  """
  cursor = g.conn.execute(sql, (username))
  user = cursor.fetchone()
  if user is None:
    sql = """
      SELECT COUNT(*) FROM users;
    """
    cursor = g.conn.execute(sql)
    count = cursor.fetchone().count + 1

    sql = """
      INSERT INTO users VALUES 
      (%s, %s)
    """
    cursor = g.conn.execute(sql, (count, username))
    userId = count;
  else:
    userId = user[0]
    
  session['logged_in'] = True
  session['userId'] = userId
  session['username'] = username
  cursor.close()
  flash('You have been logged in')
  return redirect(url_for('index'))
      
@app.route('/logout')
def logout():
  session.pop('logged_in', None)
  session.pop('userId', None)
  session.pop('username', None)
  flash('You were logged out')
  return redirect(url_for('index'))

#User profile page template
@app.route('/user/<u_id>', methods = ["POST", "GET"])
def user(u_id):
  result = []
  u = {}
  #user info
  cursor = g.conn.execute("SELECT U.username FROM users U WHERE U.id = %s", (u_id))
  result = cursor.fetchone()
  if result is None: 
    return render_template("404.html")
  u['name'] = result['username']
  

  #posted recipes
  recipes = []
  result = []
  sql_recipes = """SELECT name, id FROM recipes WHERE user_posted = %s"""
  cursor = g.conn.execute(sql_recipes, (u_id))
  for result in cursor:
    if result is not None:
      recipes.append(result)
  if cursor is None: 
    recipes = [["N/A"]]
  u['recipes'] = recipes
  

  #saved recipes
  faves = []
  result = []
  sql_fave = """SELECT R.name, R.id
      FROM user_favorites UF, recipes R
      WHERE R.id = UF.recipe_id AND UF.user_id = %s"""
  cursor = g.conn.execute(sql_fave,(u_id))
  for result in cursor:
    if result is not None:
      faves.append(result)
  if cursor is None: 
    faves = [["N/A"]]
  u['fave'] = faves
  
  
  #grocery list
  grocery = []
  result = []
  sql_list = """SELECT I.name
      FROM user_grocery UG, ingredients I
      WHERE UG.ingredient_id = I.id AND UG.user_id = %s"""
  cursor = g.conn.execute(sql_list, (u_id))
  for result in cursor:
    if result is not None:
      grocery.append(result['name'])
  u['grocery'] = grocery
  
  
  #ingredient suggestions
  suggestions=[]
  result = []
  sql_sugg = """SELECT I.name
      FROM ingredients I, user_favorites UF, recipe_ingredients RI
      WHERE I.id = RI.ingredient_id AND UF.recipe_id = RI.recipe_id AND UF.user_id = %s AND I.id 
          NOT IN(SELECT I2.id
                FROM user_grocery UF, ingredients I2
                WHERE I2.id = UF.ingredient_id)"""
  cursor = g.conn.execute(sql_sugg, (u_id))
  for result in cursor:
    if result is not None:
      suggestions.append(result['name'])
  u['sugg']=suggestions
  #add ingredients to grocery list
  
  
  #close
  print u
  cursor.close()
  return render_template('user.html', **u)

# Recipe Page Template
@app.route('/recipePage/<r_id>', methods = ["POST", "GET"])
def recipePage(r_id):
  result = []
  #recipe info
  cursor = g.conn.execute("SELECT * FROM recipes r WHERE r.id = %s", (r_id))
  result = cursor.fetchone()
  if result is None:
    return render_template("404.html")

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
  result = cursor.fetchone()
  r['cuisine'] = result[0]
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
    sql_comments = """SELECT U.username, U.id, UR.rating, UR.description
          FROM users U, user_reviews UR
          WHERE U.id = UR.user_id AND UR.recipe_id = %s"""
    cursor = g.conn.execute(sql_comments, (r_id))
    result = []
    for result in cursor:
      if result is not None:
        if result['description'] is not None:
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
