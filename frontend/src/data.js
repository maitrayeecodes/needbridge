// Category ids match your CSV files exactly. The third value is a small icon drawing.
export const CATS = [
  ['notebooks', 'Notebooks', 'M6 3h12v18H6zM9 7h6M9 11h6'],
  ['school_bag', 'School bags', 'M6 8h12l1 12H5zM9 8V6a3 3 0 016 0v2'],
  ['textbooks', 'Textbooks', 'M2 9l10-5 10 5-10 5zM6 11v5c3 2 9 2 12 0v-5'],
  ['geometry_box', 'Geometry boxes', 'M4 16L16 4l4 4L8 20zM8 12l2 2M11 9l2 2M14 6l2 2'],
  ['storybooks', 'Storybooks', 'M4 5h6a2 2 0 012 2v12a2 2 0 00-2-2H4zM20 5h-6a2 2 0 00-2 2v12a2 2 0 012-2h6z'],
  ['stationery', 'Stationery', 'M4 20l1-5L16 4l4 4L9 19zM14 6l4 4'],
  ['clothing', 'Clothing', 'M8 4l4 2 4-2 4 4-3 3v9H7v-9L4 8z'],
  ['footwear', 'Footwear', 'M3 16c4 0 6-2 8-5l3 4 7 2v3H3z'],
  ['toys', 'Toys', 'M12 3a4 4 0 100 8 4 4 0 000-8zM5 14h14v7H5z'],
  ['school_supplies', 'Other school supplies', 'M5 4h14v16H5zM8 8h8M8 12h8'],
]

export const AREAS = ['Kranti Chowk', 'Cidco', 'Garkheda', 'Osmanpura', 'Jalna Road',
  'Jawahar Colony', 'Padegaon', 'Satara Parisar', 'Harsul', 'Waluj']

export const ICONS = {
  shield: 'M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6zM9 12l2 2 4-4',
  pin: 'M12 21s7-6 7-11a7 7 0 10-14 0c0 5 7 11 7 11zM9.5 10a2.5 2.5 0 105 0 2.5 2.5 0 10-5 0',
  check: 'M12 3a9 9 0 100 18 9 9 0 000-18zM8 12l3 3 5-6',
}

// One short, warm line per category, shown on each need card
export const WHY = {
  notebooks: 'A fresh page for every dream written down.',
  school_bag: 'The first-day-of-school feeling, carried on a shoulder.',
  textbooks: 'A window to everything they are curious about.',
  geometry_box: 'The tools to measure, draw and imagine.',
  storybooks: 'Bedtime stories for children who have none.',
  stationery: 'Small things that make a school day easier.',
  clothing: 'Comfort and confidence for every school day.',
  footwear: 'A good pair for every step ahead.',
  toys: 'A little joy belongs in every childhood.',
  school_supplies: 'Useful essentials that help learning happen.',
}

export const HOW = {
  give: [
    ['List it', 'Photos, condition, quantity', 'Tell us what you have',
      [['Item', '3 school bags'], ['Condition', 'Good, no tears'], ['Pickup area', 'Cidco, Chhatrapati Sambhajinagar'], ['Ages it suits', '6 to 12']],
      'Your exact home address is never shown publicly.'],
    ['Match it', 'See needs that fit, and why', 'Needs that fit your bags',
      [['Asha School · Cidco', 'about 2 km'], ['Sahas Learning Centre · Garkheda', 'about 4 km'], ['Seva Vidyalaya · Padegaon', 'about 5 km']],
      'Good match: your bags fit the request, the age range and the condition.'],
    ['Agree a handover', 'Pick a time and place', 'Plan the handover',
      [['Organisation', 'Asha School (verified)'], ['When', 'Saturday, 10:00 am'], ['Where', 'School gate'], ['Who travels', 'You drop off']],
      'Either side can reschedule or cancel with a reason.'],
    ['Confirm it', 'Both sides confirm receipt', 'Track every step',
      [['Listed', 'Done'], ['Matched', 'Done'], ['Handover scheduled', 'Done'], ['Received', 'Waiting for the school to confirm'], ['Completed', 'After both confirm']],
      'An item only counts as donated once the organisation confirms it arrived.'],
  ],
  org: [
    ['Register', 'Share your organisation’s details', 'Create your organisation',
      [['Name', 'Asha School'], ['Type', 'School'], ['Area', 'Cidco, Chhatrapati Sambhajinagar'], ['Documents', 'Registration certificate']],
      'Children never need accounts. A responsible adult manages requests.'],
    ['Get verified', 'Our team reviews your documents', 'Verification',
      [['Documents', 'In review'], ['Contact person', 'Checked'], ['Status', 'Verified: needs can go live']],
      'Verification checks identity and registration. It is not a guarantee of every handover.'],
    ['Post a need', 'Say exactly what you need', 'New need',
      [['Item', 'Notebooks'], ['Quantity', '20'], ['Ages', '6 to 12'], ['Handover', 'Drop-off welcome']],
      'Progress such as 12 of 20 fulfilled is calculated from confirmed receipts only.'],
    ['Receive and confirm', 'Accept offers, confirm arrival', 'Incoming offer',
      [['Offer', '12 notebooks, Cidco'], ['Donor', 'Verified neighbour'], ['Action', 'Accept or decline with a reason']],
      'Confirm receipt to complete the donation and update your progress.'],
  ],
}