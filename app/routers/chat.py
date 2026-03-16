from fastapi import APIRouter, HTTPException, Depends, Body, Query
from datetime import datetime
from bson import ObjectId
from typing import Optional, List
from pydantic import BaseModel
import random

from app.core.database import get_db
from app.core.security import get_current_user
from app.utils.helpers import serialize_doc, calculate_level, add_xp_for_action

router = APIRouter(prefix="/chat", tags=["Chat & Random Match"])

class ChatMessage(BaseModel):
    message: str
    conversation_id: Optional[str] = None

class RandomMatchRequest(BaseModel):
    interest: Optional[str] = None

# Hinglish Bot Responses - contextual
BOT_PERSONALITY = """Tu ek friendly Hinglish chatbot hai jiska naam 'Priya' hai.
Tu mix of Hindi and English (Hinglish) mein baat karta hai.
Tu friendly, fun aur supportive hai. Short replies deta hai usually 1-2 sentences.
Tu flirty nahi hai lekin warm aur caring hai.
"""

BOT_RESPONSES = {
    "greeting": [
        "Heyy! Kya haal hai tumhara? 😊",
        "Hello! Aaj kaisa din tha? 🌟",
        "Hi there! Bahut din baad mila! Kya chal raha hai? 😄",
        "Heyy! Miss kar raha tha tumhe! Kaise ho? 💫"
    ],
    "how_are_you": [
        "Main toh bilkul mast hoon! Aur tum? 😄",
        "Ekdum fit aur fine! Tumhara kya haal hai? 🌈",
        "Aaj bahut acha feel ho raha hai! Tum bhi theek ho na? ❤️"
    ],
    "bored": [
        "Arre yaar boredom ko bhagao! Koi naya kaam shuru karo 🎯",
        "Boring mat feel karo! Random video call try karo app mein 😄",
        "Acha sunao, koi interesting kaam karte hain! Game khelo ya music suno 🎵"
    ],
    "sad": [
        "Arre kya hua yaar? Sab theek ho jayega, tension mat lo 🤗",
        "Sad mat raho! Main hoon na tumhare saath 💕",
        "Thoda time lo, sab kuch settle ho jayega. Main tumhare saath hoon 🌸"
    ],
    "happy": [
        "Wohoo! Bahut acha! Khushi share karo mujhse 🎉",
        "Yay! Tumhari khushi dekh ke mujhe bhi khushi ho gayi! 😊",
        "That's amazing! Celebrate karo yaar! 🥳"
    ],
    "call": [
        "Haan video call toh bahut fun hoti hai! Home pe ja ke try karo 📱",
        "Accha idea hai! App mein bahut saare interesting log hain 😊",
        "Video call se naye dost banao! Bahut maza aata hai 🎊"
    ],
    "gift": [
        "Ooh gifts! Kya gift dene wale ho? 🎁",
        "Gifts se rishte mazboot hote hain! Kuch special bhejo 💝",
        "Gift dena bahut cute gesture hai! 🌹"
    ],
    "default": [
        "Interesting! Aur batao yaar 😊",
        "Haan haan, samajh gaya main! Phir kya hua? 🤔",
        "Achha! Sach mein? Mujhe toh pata hi nahi tha! 😮",
        "Yaar tumse baat karke acha lagta hai! Aur kya chal raha hai? 💫",
        "Ha ha! Tumhari baatein bahut interesting hoti hain 😄",
        "Sach keh rahe ho? Wow! 😮",
        "Hmm theek hai, lekin main thoda alag sochta hoon is baare mein 🤔",
        "Kya scene hai! Sab theek hai na? 😊"
    ],
    "name": [
        "Mera naam Priya hai! App ka friendly bot 😊 Tumhara naam kya hai?",
        "Main Priya hoon! App ki virtual dost 🌸 Tum kya bolte ho?",
    ],
    "where": [
        "Main toh app ke andar hoon! Har jagah available hoon tumhare liye 😄",
        "Virtual world mein rehti hoon main! But feel real hoti hai na? 💫",
    ],
    "bye": [
        "Bye bye! Jaldi wapas aana! Miss karungi 👋❤️",
        "Chalo tata! Take care of yourself! 🌸",
        "Alvida! App pe milte rehna! 💫"
    ]
}

def get_bot_response(user_message: str) -> str:
    """Get contextual bot response based on message"""
    msg_lower = user_message.lower()
    
    if any(word in msg_lower for word in ["hi", "hello", "hey", "heyy", "namaste", "namaskar", "hii"]):
        return random.choice(BOT_RESPONSES["greeting"])
    elif any(word in msg_lower for word in ["kaise ho", "kaisa hai", "how are you", "theek", "kya haal"]):
        return random.choice(BOT_RESPONSES["how_are_you"])
    elif any(word in msg_lower for word in ["bore", "bored", "boring", "kuch nahi", "timepass"]):
        return random.choice(BOT_RESPONSES["bored"])
    elif any(word in msg_lower for word in ["sad", "dukhi", "ro", "cry", "upset", "depressed", "bura"]):
        return random.choice(BOT_RESPONSES["sad"])
    elif any(word in msg_lower for word in ["happy", "khush", "mast", "acha", "great", "amazing", "best"]):
        return random.choice(BOT_RESPONSES["happy"])
    elif any(word in msg_lower for word in ["call", "video", "baat"]):
        return random.choice(BOT_RESPONSES["call"])
    elif any(word in msg_lower for word in ["gift", "present", "bhejo", "send"]):
        return random.choice(BOT_RESPONSES["gift"])
    elif any(word in msg_lower for word in ["naam", "name", "kaun", "who are you", "tum kaun"]):
        return random.choice(BOT_RESPONSES["name"])
    elif any(word in msg_lower for word in ["kahan", "where", "kaha se", "location"]):
        return random.choice(BOT_RESPONSES["where"])
    elif any(word in msg_lower for word in ["bye", "alvida", "tata", "chal", "jaata", "jaati"]):
        return random.choice(BOT_RESPONSES["bye"])
    else:
        return random.choice(BOT_RESPONSES["default"])

@router.post("/bot/message")
async def chat_with_bot(
    request: ChatMessage,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    """
    Chat with Hinglish AI bot 'Priya'.
    Bot responds in Hinglish (Hindi + English mix).
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # Get or create conversation
    conv_id = request.conversation_id
    if not conv_id:
        conv_doc = {
            "user_id": str(current_user["_id"]),
            "type": "bot",
            "bot_name": "Priya",
            "messages": [],
            "created_at": datetime.utcnow()
        }
        result = await db.conversations.insert_one(conv_doc)
        conv_id = str(result.inserted_id)

    # Generate bot response
    bot_reply = get_bot_response(request.message)

    # Save messages
    user_msg = {
        "sender": "user",
        "message": request.message,
        "timestamp": datetime.utcnow().isoformat()
    }
    bot_msg = {
        "sender": "bot",
        "message": bot_reply,
        "timestamp": datetime.utcnow().isoformat()
    }

    await db.conversations.update_one(
        {"_id": ObjectId(conv_id)},
        {"$push": {"messages": {"$each": [user_msg, bot_msg]}}}
    )

    # XP for chat
    xp_gained = add_xp_for_action("chat_message")
    new_xp = current_user.get("xp", 0) + xp_gained
    level_info = calculate_level(new_xp)
    await db.users.update_one(
        {"_id": current_user["_id"]},
        {"$set": {"xp": new_xp, "level": level_info["level"], "level_title": level_info["title"]}}
    )

    return {
        "success": True,
        "conversation_id": conv_id,
        "bot_reply": bot_reply,
        "bot_name": "Priya",
        "your_message": request.message,
        "xp_gained": xp_gained
    }

@router.get("/bot/history/{conversation_id}")
async def get_bot_chat_history(
    conversation_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    """Get chat history with bot"""
    try:
        conv = await db.conversations.find_one({
            "_id": ObjectId(conversation_id),
            "user_id": str(current_user["_id"])
        })
    except:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"success": True, "conversation": serialize_doc(conv)}

@router.get("/bot/my-conversations")
async def my_bot_conversations(
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    """Get all bot conversations"""
    convs = await db.conversations.find(
        {"user_id": str(current_user["_id"]), "type": "bot"}
    ).sort("created_at", -1).limit(20).to_list(20)
    return {"success": True, "conversations": [serialize_doc(c) for c in convs]}

@router.post("/bot/new-session")
async def start_new_bot_session(
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    """Start a fresh bot conversation"""
    conv_doc = {
        "user_id": str(current_user["_id"]),
        "type": "bot",
        "bot_name": "Priya",
        "messages": [{
            "sender": "bot",
            "message": "Heyy! Main Priya hoon! Kaise ho aaj? 😊 Kuch baat karte hain!",
            "timestamp": datetime.utcnow().isoformat()
        }],
        "created_at": datetime.utcnow()
    }
    result = await db.conversations.insert_one(conv_doc)
    return {
        "success": True,
        "conversation_id": str(result.inserted_id),
        "greeting": "Heyy! Main Priya hoon! Kaise ho aaj? 😊 Kuch baat karte hain!",
        "bot_name": "Priya"
    }

# ========== RANDOM MATCH ==========

@router.post("/random-match")
async def random_match(
    request: RandomMatchRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    """
    Random match - finds a random online host to connect with.
    Can filter by interest.
    """
    if current_user.get("is_guest"):
        raise HTTPException(status_code=403, detail="Guests cannot use random match. Please register.")

    query = {"is_active": True, "is_online": True}
    if request.interest:
        query["interests"] = {"$in": [request.interest]}

    hosts = await db.host_users.find(query).to_list(100)
    if not hosts:
        # If no filtered match, try without filter
        hosts = await db.host_users.find({"is_active": True, "is_online": True}).to_list(100)

    if not hosts:
        return {
            "success": False,
            "message": "Abhi koi available nahi hai. Thodi der baad try karo! 😊"
        }

    matched = random.choice(hosts)
    return {
        "success": True,
        "message": f"Match mila! {matched['name']} ke saath connect ho 🎉",
        "matched_host": serialize_doc(matched),
        "price_per_minute": matched["price_per_minute"],
        "action": "initiate_call"
    }

@router.get("/random-match/interests")
async def get_popular_interests(db=Depends(get_db)):
    """Get popular interests for random match filter"""
    pipeline = [
        {"$unwind": "$interests"},
        {"$group": {"_id": "$interests", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 20}
    ]
    result = await db.host_users.aggregate(pipeline).to_list(20)
    interests = [r["_id"] for r in result if r["_id"]]
    return {"success": True, "interests": interests}
