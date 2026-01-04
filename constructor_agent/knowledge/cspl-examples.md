# CSPL Examples

Prompt → Understanding → Change

## Workflow

**Prompt:** "Before booking shoes, ask the user for their shoe size"

**Understanding:** Workflow-specific data collection → add fetch step to BookShoes workflow

**Change:**
```yaml
- id: ask_shoe_size
  action: fetch
  field: shoe_size
  comment: Must be a number
```

---

**Prompt:** "if shoe size is greater than 7, reply that we do not sell those sizes, if less ask for what do they like- colors, models, brands"

**Understanding:** currently there is a fetch, we should change it to fetch_with_condition and we should also ask what happens if the size is exactly 7
**Agent Clarification Question:** what happens if the size is exactly 7? user: ask what do they like.

**Change:**
before:
```yaml
- id: ask_shoe_size
  action: fetch
  field: shoe_size
  comment: Must be a number
```

after:
```yaml
- id: ask_shoe_size
  action: fetch_with_condition
  field: shoe_size
  comment: Must be a number
  condition: "{shoe_size} > 7"
  then:
  - id: reply_more_than_7
    action: reply
    message: "We do not sell those sizes."
  else:
  - id: ask_shoe_preferences
    action: fetch_with_message
    field: shoe_preferences
    message: "What shoes do you like? Any specific brand? Model? Colors?"
```

---

**Prompt:** "If the shoe size is lower then 5 then tell them they get a 20% discout"

**Understanding:** we need to add another condition after fetching the the shoe size, so inside the branch of if shoe size is less then 7 we will add this additional condition. we need to tell them they get a 20% discout but also keep it in memory so that later we will adjust the price with the discount

**Change:**
```yaml
- id: ask_shoe_size
  action: fetch_with_condition
  field: shoe_size
  comment: Must be a number
  condition: "{shoe_size} > 7"
  then:
  - id: reply_more_than_7
    action: reply
    message: "We do not sell those sizes."
  else:
  - id: check_discount_eligibility
    action: conditional
    condition: "{shoe_size} < 5"
    then:
    - id: set_discount
      action: set_variable
      variable: discount_percentage
      value: 20
    - id: inform_discount
      action: reply
      message: "Great news! You get a 20% discount on your purchase."
  - id: ask_shoe_preferences
    action: fetch_with_message
    field: shoe_preferences
    message: "What shoes do you like? Any specific brand? Model? Colors?"
```

---


---



---

---

## Instruction

**Prompt:** "Calculate the total price by summing all item prices and multiplying by the number of items"

**Understanding:** Complex calculation that requires multiple steps → use instruction action

**Change:**
```yaml
- id: calculate_total_price
  action: instruction
  instruction: |
    Calculate the total price for the order:
    1. Sum all prices from the items list
    2. Multiply the sum by the number_of_items
    3. Return the total price
  set_variables:
  - total_price
```

---

**Prompt:** "Count how many passengers are in the reservation"

**Understanding:** Need to count items in a list → use instruction to get length

**Change:**
```yaml
- id: count_passengers
  action: instruction
  instruction: |
    Count the number of passengers from the passengers variable in memory.
    The passengers variable is a list of Passenger objects that was set from get_reservation_details.
    Set number_of_passengers to the length of this list.
  set_variable: number_of_passengers
```

---

**Prompt:** "Extract flight numbers and dates from the reservation flights list"

**Understanding:** Need to extract specific fields from complex data structures → use instruction

**Change:**
```yaml
- id: extract_flight_info
  action: instruction
  instruction: |
    Extract the flight numbers and dates from the reservation_flights.
    The reservation_flights is a list of ReservationFlight objects, each containing:
    - flight_number: The flight number (e.g., "HAT001")
    - date: The flight date in YYYY-MM-DD format

    Set the following variables:
    - flight_numbers: A list of all flight numbers from the reservation
    - flight_dates: A list of all flight dates from the reservation
  set_variables:
  - flight_numbers
  - flight_dates
```

---

**Prompt:** "Check if the booking was made within the last 24 hours"

**Understanding:** Complex time calculation → use instruction with detailed steps

**Change:**
```yaml
- id: check_booking_within_24hr
  action: instruction
  instruction: |
    Check if the reservation was created within the last 24 hours.

    Steps:
    1. Get the created_at timestamp (format: YYYY-MM-DDTHH:MM:SS)
    2. Get today_date from memory (format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
    3. Calculate the time difference between today_date and reservation_created_at
    4. If the difference is less than 24 hours, set booking_within_24hr to true, else false

    Note: You may need to parse the datetime strings and calculate hours difference.
    Set booking_within_24hr variable to true or false.
  set_variable: booking_within_24hr
```

---

## Loop

**Prompt:** "For each reservation in the list, get its details and collect all the information"

**Understanding:** Need to iterate over a list and perform an action on each item → use loop with subaction

**Change:**
```yaml
- id: fetch_all_reservation_details
  action: loop
  loop_over: reservations_list
  loop_variable: reservation_id
  set_variable: all_reservation_details
  subaction:
    action: use_tool
    tool_name: get_reservation_details
    input: ["{{ reservation_id }}"]
    set_variables:
    - reservation_id
    - origin
    - destination
```

---

## Use Tool

**Prompt:** "Search for available flights and store the results in a variable called flight_search_results"

**Understanding:** Need to call a tool and assign its result to a variable with a custom name → use use_tool with set_variables. The agent should check what tools are available and what fields they return to properly map the results.

**Change:**
```yaml
- id: search_flights
  action: use_tool
  tool_name: search_direct_flight
  input: ["{{ origin }}", "{{ destination }}", "{{ date }}"]
  set_variables:
  - flight_search_results: result
```

---

**Prompt:** "Get reservation details and extract the cabin and flights, but rename flights to reservation_flights"

**Understanding:** Need to call a tool and map specific fields from the result to custom variable names → use set_variables with name:value format. The agent should check the tool's return structure to know which fields are available.

**Change:**
```yaml
- id: get_reservation_details
  action: use_tool
  tool_name: get_reservation_details
  input: ["{{ reservation_id }}"]
  set_variables:
  - cabin
  - reservation_flights: flights
```

---

## Multi-Edit

**Prompt:** "when we ask for shoe size, we need to always ask it in US sizes"

**Understanding:** we need to find in the workflow all of the places that have fetch shoe size, and add a comment that we have to get it in US size.
---

## Constants

**Prompt:** "Before doing anything, we have to know if the customer is a female or male"

**Understanding:** Always required, not workflow-specific → default prerequisite

**Change:**
```yaml
# constants.yaml
default_prerequisites:
  - user_id
  - gender
```

---

**Prompt:** "Always ask for the user's account number before doing anything else"

**Understanding:** Always required → default prerequisite

**Change:**
```yaml
# constants.yaml
default_prerequisites:
  - user_id
  - account_number
```

---

## Tone

**Prompt:** "Make the agent more friendly and use emojis in responses"

**Understanding:** Communication style change → update tone field

**Change:**
```yaml
# tone.yaml
tone: "Be friendly, warm, and use emojis when appropriate 😊"
```

---

**Prompt:** "Be enthusiastic about travel insurance and use emojis"

**Understanding:** Communication style change → update tone field

**Change:**
```yaml
# tone.yaml
tone: "Be enthusiastic and helpful, use emojis to make interactions more engaging ✈️ 🎉"
```

---