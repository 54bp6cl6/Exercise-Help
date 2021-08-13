import os
import sys
import logging
import json
import datetime

from linebot import (
	LineBotApi, WebhookHandler
)
from linebot.models import (
	MessageEvent, TextMessage, TextSendMessage,
	SourceUser, SourceGroup, SourceRoom,
	TemplateSendMessage, ConfirmTemplate, MessageAction,
	ButtonsTemplate, ImageCarouselTemplate, ImageCarouselColumn, URIAction,
	PostbackAction, DatetimePickerAction,
	CameraAction, CameraRollAction, LocationAction,
	CarouselTemplate, CarouselColumn, PostbackEvent,CarouselContainer,
	StickerMessage, StickerSendMessage, LocationMessage, LocationSendMessage,
	ImageMessage, VideoMessage, AudioMessage, FileMessage,
	UnfollowEvent, FollowEvent, JoinEvent, LeaveEvent, BeaconEvent,
	FlexSendMessage, BubbleContainer, ImageComponent, BoxComponent,
	TextComponent, SpacerComponent, IconComponent, ButtonComponent,
	SeparatorComponent, QuickReply, QuickReplyButton,
	ImageSendMessage)

import firebase_admin
from firebase_admin import (
	credentials,firestore
)

line_bot_api = LineBotApi('7IpCXdd6oXyXmuvZ0qhs/WvCbbMH09iOp4a51EbHHGVmH/Vheo7OvnZg6aB9xKftJcz/NvTVNLjFCq9eOGcm8mThoLNB3zeemkg4xB0Xwm2Cb7XsuBAjlol3DpfGBuJUklydLvNhFX58ik/WE5r4mAdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('b129e0793dd78d151e5a14c1e1ff9f19')

cred = credentials.ApplicationDefault()
firebase_admin.initialize_app(cred, {'projectId': 'exercisehelp-f3ae5'})

def callback(request):
	try:
		event = get_event(request)

		if event['type'] == 'message':
			if event['message']['type'] == 'text':
				element = event['message']['text'].strip().split()
				if element[0].isdecimal():
					#檢查是否有鎖定項目
					#新增紀錄
					item = db_get_training(event['source']['userId'])
					if item != '':
						weight = int(element[0])
						times = 1
						if len(element) > 1:
							times = int(element[1])
						best = db_get_best(event['source']['userId'], item)
						beyond = False
						if weight > best[0] or (weight >= best[0] and times > best[1]):beyond = True
						line_bot_api.reply_message(event['replyToken'], add_exercise_flex(item, weight, times, beyond))
						db_add_record(event['source']['userId'], item, weight, times)
					else:
						line_bot_api.reply_message(event['replyToken'], exercise_flex())
				elif event['message']['text'] ==  "結算":
					end_exercise(event['replyToken'], event['source']['userId'])
				elif event['message']['text'] == "新增":
					line_bot_api.reply_message(event['replyToken'], 
						TextSendMessage(text="請參照以下格式輸入指令:new item_name part type"))
				elif element[0] == "new":
					try:
						data = {
							u'部位': element[2],
							u'類型': element[3]
						}
						db = firestore.client()
						db.collection(u'exercise').document(element[1]).set(data)
					except:
						line_bot_api.reply_message(event['replyToken'], 
							TextSendMessage(text="參數錯誤，請參照以下格式輸入指令:new item_name part type"))
				else:
					#關鍵字搜尋
					target = db_search(event['message']['text'])
					if len(target.keys()) == 1:
						choose_exercise_sop(event['replyToken'], event['source']['userId'], list(target.keys())[0])
					elif len(target.keys()) > 1:
						line_bot_api.reply_message(event['replyToken'], exercise_flex(target=target))
					else:
						line_bot_api.reply_message(event['replyToken'], exercise_flex())

		elif event['type'] == 'postback':
			element = event['postback']['data'].split(',')
			if element[0] == 'choose':
				choose_exercise_sop(event['replyToken'], event['source']['userId'], element[1])
			elif element[0] == 'basic':
				line_bot_api.reply_message(event['replyToken'], exercise_flex())
			elif element[0] == 'same':
				line_bot_api.reply_message(event['replyToken'], add_exercise_flex(element[1], int(element[2]), int(element[3]), False))
				db_add_record(event['source']['userId'], element[1], int(element[2]), int(element[3]))
			elif element[0] == 'delete':
				ref = firestore.client().collection(u'record').where(u'userid', u'==', event['source']['userId']).where(u'item', u'==', element[1]).where(u'weight', u'==', int(element[2])).where(u'times', u'==', int(element[3])).stream()
				for doc in ref:
					line_bot_api.reply_message(event['replyToken'], delete_record_flex(element[1],element[2],element[3]))
					doc.reference.delete()
					break
	except:
		logging.error(sys.exc_info())
		return 'ERROR'
	return 'OK'

def end_exercise(replyToken, userId):
	db = firestore.client()
	records = db.collection(u'record').where(u'userid', u'==', userId).stream()
	exercise_dict = {}
	del_dict = {}
	for doc in records:
		record = doc.to_dict()
		if record['date'].date() == datetime.datetime.now().date():
			if record['item'] not in exercise_dict: exercise_dict[record['item']] = []
			exercise_dict[record['item']].append(record)
		else:
			if record['item'] not in del_dict: del_dict[record['item']] = []
			del_dict[record['item']].append(doc)
	line_bot_api.reply_message(replyToken, end_exercise_flex(exercise_dict))
	for key in del_dict.keys():
		best = db_get_best(userId, key)
		max_weight = best[0]
		times = best[1]
		for doc in del_dict[key]:
			record = doc.to_dict()
			if record['weight'] > max_weight: max_weight = record['weight']
			elif record['weight'] == max_weight and record['times'] >= times: times = record['times']
			else: doc.reference.delete()

def end_exercise_flex(exercise_dict):
	background_color = "#07529d"
	title_color = "#ffffff"
	text_color = "#bababa"
	box_list = [
		TextComponent(
			text='結算成績',
			weight="bold",
			size="xl",
			color=title_color
		),
		BoxComponent(
			layout="baseline",
			spacing="sm",
			contents=[
				TextComponent(text="訓練項目",color=text_color,size="md",flex=2),
				TextComponent(text="重量",wrap=True,color=text_color,size="md", flex=1),
				TextComponent(text="次數",wrap=True,color=text_color,size="md",flex=1)
			]
		)
	]
	for i in exercise_dict.values():
		for record in i:
			box_list.append(
				BoxComponent(
					layout="baseline",
					spacing="sm",
					contents=[
						TextComponent(text=record['item'],color=text_color,size="md",flex=2),
						TextComponent(text=str(record['weight']),wrap=True,color=text_color,size="md",flex=1),
						TextComponent(text=str(record['times']),wrap=True,color=text_color,size="md",flex=1)
					]
				)
			)
	bubble = BubbleContainer(
		body=BoxComponent(
			layout="vertical",
			background_color=background_color,
			spacing='sm',
			contents=box_list
		)
	)
	return FlexSendMessage(alt_text="結算清單", contents=bubble)


def delete_record_flex(item, weight, times):
	background_color = "#8f2b24"
	title_color = "#ffffff"
	text_color = "#aaaaaa"
	bubble = BubbleContainer(
		body=BoxComponent(
			layout="vertical",
			background_color=background_color,
			spacing='sm',
			contents=[
				TextComponent(
					text='已刪除紀錄',
					weight="bold",
					size="xl",
					color=title_color
				),
				BoxComponent(
					layout="vertical",
					margin="lg",
					spacing="sm",
					contents=[
						BoxComponent(
							layout="baseline",
							spacing="sm",
							contents=[
								TextComponent(text="刪除項目",color=text_color,size="md"),
								TextComponent(text=item,wrap=True,color=text_color,size="md")
							]
						),
						BoxComponent(
							layout="baseline",
							spacing="sm",
							contents=[
								TextComponent(text="重量",color=text_color,size="md"),
								TextComponent(text=str(weight),wrap=True,color=text_color,size="md")
							]
						),
						BoxComponent(
							layout="baseline",
							spacing="sm",
							contents=[
								TextComponent(text="次數",color=text_color,size="md"),
								TextComponent(text=str(times),wrap=True,color=text_color,size="md")
							]
						)
					]
				)
			]
		)
	)
	return FlexSendMessage(alt_text="健身項目選單", contents=bubble)

def add_exercise_flex(item, weight, times, beyond):
	background_color = "#444440"
	title_color = "#ffffff"
	text_color = "#aaaaaa"
	box = SpacerComponent(size='sm')
	if beyond: 
		box = BoxComponent(
			layout="baseline",
			spacing="sm",
			contents=[
				TextComponent(text="你突破最高紀錄了喔!!",color=text_color,size="md")
			]
		)
	bubble = BubbleContainer(
		body=BoxComponent(
			layout="vertical",
			background_color=background_color,
			spacing='sm',
			contents=[
				TextComponent(
					text=item,
					weight="bold",
					size="xl",
					color=title_color
				),
				BoxComponent(
					layout="vertical",
					margin="lg",
					spacing="sm",
					contents=[
						BoxComponent(
							layout="baseline",
							spacing="sm",
							contents=[
								TextComponent(text="重量",color=text_color,size="md"),
								TextComponent(text=str(weight),wrap=True,color=text_color,size="md")
							]
						),
						BoxComponent(
							layout="baseline",
							spacing="sm",
							contents=[
								TextComponent(text="次數",color=text_color,size="md"),
								TextComponent(text=str(times),wrap=True,color=text_color,size="md")
							]
						),
						BoxComponent(
							layout="baseline",
							spacing="sm",
							contents=[
								TextComponent(text="訓練量",color=text_color,size="md"),
								TextComponent(text=str(weight*times),wrap=True,color=text_color,size="md")
							]
						),
						box
					]
				)
			]
		),
		footer=BoxComponent(
			layout="vertical",
			spacing="sm",
			background_color=background_color,
			contents=[
				ButtonComponent(
					style="primary",
					height="sm",
					color=background_color,
					action=PostbackAction(label="新增一條相同紀錄", data='same,{},{},{}'.format(item,weight,times))
				),
				ButtonComponent(
					style="primary",
					height="sm",
					color=background_color,
					action=PostbackAction(label="刪除此紀錄", data='delete,{},{},{}'.format(item,weight,times))
				),
				SpacerComponent(
					size='sm'
				)
			]
		)
	)
	return FlexSendMessage(alt_text="健身項目選單", contents=bubble)

def choose_exercise_sop(replyToken, userId, item):
	best = db_get_best(userId, item)
	line_bot_api.reply_message(replyToken, choose_exercise_flex(item,best[0],best[1]))
	db_choose_exercise(userId, item)

def choose_exercise_flex(item, max_weight, times):
	background_color = "#444440"
	title_color = "#ffffff"
	text_color = "#aaaaaa"
	bubble = BubbleContainer(
		body=BoxComponent(
			layout="vertical",
			background_color=background_color,
			spacing='sm',
			contents=[
				TextComponent(
					text=item,
					weight="bold",
					size="xl",
					color=title_color
				),
				BoxComponent(
					layout="vertical",
					margin="lg",
					spacing="sm",
					contents=[
						BoxComponent(
							layout="baseline",
							spacing="sm",
							contents=[
								TextComponent(text="最大重量",color=text_color,size="lg"),
								TextComponent(text=str(max_weight),wrap=True,color=text_color,size="lg")
							]
						),
						BoxComponent(
							layout="baseline",
							spacing="sm",
							padding_bottom='md',
							contents=[
								TextComponent(text="次數",color=text_color,size="lg"),
								TextComponent(text=str(times),wrap=True,color=text_color,size="lg")
							]
						),
						TextComponent(text="輸入: 重量 次數 來增加新訓練紀錄",color=text_color,size="sm"),
						TextComponent(text="例如: 60 5",color=text_color,size="sm")
					]
				)
			]
		),
		footer=BoxComponent(
			layout="horizontal",
			spacing="sm",
			background_color=background_color,
			contents=[
				ButtonComponent(
					style="primary",
					height="sm",
					color=background_color,
					action=PostbackAction(label="更換", data='basic')
				),
				SpacerComponent(
					size='sm'
				)
			]
		)
	)
	return FlexSendMessage(alt_text="健身項目", contents=bubble)

def db_get_best(userId, item):
	db = firestore.client()
	records = db.collection(u'record').where(u'userid', u'==', userId).where(u'item', u'==', item).stream()
	max_weight = 0
	times = 0
	for record in records:
		rc = record.to_dict()
		if int(rc['weight']) > max_weight: 
			max_weight = int(rc['weight'])
			times = int(rc['times'])
		elif int(rc['weight']) == max_weight and int(rc['times']) > times:
			times = int(rc['times'])
	return [max_weight, times]

def db_search(keyword):
	exercise = db_get_exercise()
	target = {}
	for key in exercise.keys():
		if key.find(keyword) >= 0 or exercise[key]['部位'] == keyword or exercise[key]['類型'] == keyword:
			target[key] = exercise[key]
	return target

def db_choose_exercise(userId, exercise_key):
	db = firestore.client()
	db.collection(u'training').document(userId).set({u'item': exercise_key})

def db_add_record(userId, item, weight, times):
	data = {
		u'userid': userId,
		u'item': item,
		u'weight': weight,
		u'date': datetime.datetime.now(),
		u'times': times
	}
	db = firestore.client()
	db.collection(u'record').add(data)

def db_get_training(userId):
	db = firestore.client()
	try:
		item = db.collection(u'training').document(userId).get().to_dict()['item']
		return item
	except:
		return ''

def db_get_exercise():
	db = firestore.client()
	docs = db.collection(u'exercise').stream()
	exercise = {}
	for doc in docs:
		text = u'{} => {}'.format(doc.id, doc.to_dict())
		exercise['{}'.format(doc.id)] = doc.to_dict()
	return exercise

def exercise_flex(target={}):
	background_color = '#444440'
	title_color = '#ffffff'
	button_color = '#fced27'
	button_font_color = 'secondary'

	def make_button_list(exercise_list):
		button_list = []
		for exercise in exercise_list:
			button_list.append(
				ButtonComponent(
					color=button_color,
					style=button_font_color,
					height='sm',
					action=PostbackAction(label=exercise, data='choose,'+exercise)
				)
			)
		return button_list

	exercise = {}
	if len(target.keys()) > 0: exercise = target
	else: exercise = db_get_exercise()
	bubbles = []
	part_list = {'胸':[],'背':[],'腿':[],'肩':[],'手':[],'腹':[]}
	for key in exercise.keys():
		part_list[exercise[key]["部位"]].append(key)
	for key in part_list.keys():
		if len(part_list[key]) > 0:
			bubbles.append(BubbleContainer(
				size='micro',
				body=BoxComponent(
					background_color=background_color,
					spacing='sm',
					layout='vertical',
					contents=([TextComponent(text=key+'部訓練', weight='bold', size='xl',align='center',color=title_color)]+make_button_list(part_list[key]))
				)
			))
	return FlexSendMessage(alt_text="健身項目選單", contents=CarouselContainer(contents=bubbles))

def get_event(request):
	body = request.get_data(as_text=True)
	print("Request body: " + body)
	event = json.loads(body)
	return event['events'][0]
