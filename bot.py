import discord, time, asyncio, requests, json
from discord.ext import commands
from solathon.core.instructions import transfer
from solathon import Client, Transaction, PublicKey, Keypair
import threading

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
LAMPORTS_PER_SOL = 1000000000

wallets = {
    "wallet_1": {
        "address": "",
        "private_key": ""
    },
    "wallet_2": {
        "address": "",
        "private_key": ""
    }
}

@bot.event
async def on_ready():
    print(f"Bot is ready. Logged in as {bot.user.name}")

def is_invalid(signature):
    url = "http://main.deez.top"
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTransaction",
        "params": [
            signature,
            "json"
        ]
    }

    response = requests.post(url, headers=headers, data=json.dumps(payload))
    
    if response.status_code == 200:
        if response.json()["result"] == None:
            return True
        return False
    else:
        return True
    
def send_transaction(pk, receiver, amount, max_retries=5):
    client = Client("http://main.deez.top:80/", True)
    sender = Keypair().from_private_key(pk)
    receiver = PublicKey(receiver)
    amount = int(amount * LAMPORTS_PER_SOL)
    
    instruction = transfer(
        from_public_key=sender.public_key,
        to_public_key=receiver,
        lamports=amount
    )
    transaction = Transaction(instructions=[instruction], signers=[sender])
    
    for attempt in range(max_retries + 1):
        try:
            result = client.send_transaction(transaction)
            return result
        except Exception as e:
            error_message = str(e)
            if "Transaction not found" in error_message or attempt < max_retries:
                print(f"Attempt {attempt + 1} failed: {error_message}. Retrying in 2 seconds...")
                time.sleep(2)
            else:
                return f"Error: {error_message}"
    
    return "Error: Max retries reached"

def get_balance(address):
    client = Client("http://main.deez.top:80/", True)
    public_key = PublicKey(address)
    balance = client.get_balance(public_key)
    return balance / LAMPORTS_PER_SOL

async def wait_for_balance_change(address, initial_balance, timeout=30, check_interval=1):
    start_time = time.time()
    client = Client("http://main.deez.top:80/", True)
    public_key = PublicKey(address)

    while time.time() - start_time < timeout:
        try:
            current_balance = client.get_balance(public_key) / LAMPORTS_PER_SOL
            if abs(current_balance - initial_balance) > 0.000001:
                return True
        except Exception as e:
            print(f"Error checking balance: {str(e)}")
        
        await asyncio.sleep(1)
    
    return False

@bot.command(name="r")
async def respond(ctx):
    try:
        initial_balance_2 = get_balance(wallets["wallet_2"]["address"])
        initial_balance_1 = get_balance(wallets["wallet_1"]["address"])
        transfer_amount = initial_balance_2 - 0.1
        
        await ctx.send(f"`Wallet 2` has `{initial_balance_2:.9f}` SOL")
        await ctx.send(f"Transferring `{transfer_amount:.9f}` SOL to `Wallet 1`")
        
        def send():
            try:
                result = send_transaction(wallets["wallet_2"]["private_key"], wallets["wallet_1"]["address"], transfer_amount)
            except Exception as e:
                print(e)

        for i in range(10):
            threading.Thread(target=send).start()
        
        await ctx.send("Waiting for transaction confirmation...")
        
        confirmed = await wait_for_balance_change(wallets["wallet_1"]["address"], initial_balance_1)
        
        if confirmed:
            await ctx.send("Transaction confirmed!")
        else:
            await ctx.send("Transaction not confirmed after 30 seconds. It may still be processing.")

        final_balance_1 = get_balance(wallets["wallet_1"]["address"])
        final_balance_2 = get_balance(wallets["wallet_2"]["address"])
        
        await ctx.send(f"`Wallet 1` now has `{final_balance_1:.9f}` SOL")
        await ctx.send(f"`Wallet 2` now has `{final_balance_2:.9f}` SOL")
    except Exception as e:
        await ctx.send(f"An error occurred: {str(e)}")

@bot.command(name="getbal")
async def fee(ctx):
    final_balance_1 = get_balance(wallets["wallet_1"]["address"])
    final_balance_2 = get_balance(wallets["wallet_2"]["address"])
    
    await ctx.send(f"`Wallet 1` has `{final_balance_1:.9f}` SOL")
    await ctx.send(f"`Wallet 2` has `{final_balance_2:.9f}` SOL")

@bot.command(name="fee")
async def fee(ctx, amount: float):
    try:
        fee_amount = amount * 1.5
        initial_balance_1 = get_balance(wallets["wallet_1"]["address"])
        initial_balance_2 = get_balance(wallets["wallet_2"]["address"])

        if initial_balance_1 < fee_amount:
            await ctx.send(f"Error: Insufficient balance in Wallet 1. Required: {fee_amount:.9f} SOL, Available: {initial_balance_1:.9f} SOL")
            return

        await ctx.send(f"Transferring `{fee_amount:.9f}` SOL from `Wallet 1` to `Wallet 2`")

        result = ""

        for i in range(10):
            if result == "" or result.startswith("Error"):
                result = send_transaction(wallets["wallet_1"]["private_key"], wallets["wallet_2"]["address"], fee_amount)

        if isinstance(result, str) and result.startswith("Error"):
            await ctx.send(f"Transaction failed: {result}, please try again")
            return

        await ctx.send(f"`https://solscan.io/tx/{result}`")
        await ctx.send("Waiting for transaction confirmation...")

        confirmed = await wait_for_balance_change(wallets["wallet_2"]["address"], initial_balance_2)

        if confirmed:
            await ctx.send("Transaction confirmed!")
            
            await asyncio.sleep(2)

            final_balance_1 = get_balance(wallets["wallet_1"]["address"])
            final_balance_2 = get_balance(wallets["wallet_2"]["address"])

            await ctx.send(f"`Wallet 1` now has `{final_balance_1:.9f}` SOL")
            await ctx.send(f"`Wallet 2` now has `{final_balance_2:.9f}` SOL")
        else:
            await ctx.send("Probably didnt go thru try again.")

    except ValueError:
        await ctx.send("Error: Please provide a valid number")
    except Exception as e:
        await ctx.send(f"An error occurred: {str(e)}")
        await ctx.send("If the transaction was confirmed earlier, it may have been processed successfully.")

bot.run("")
