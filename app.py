import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime

# Initialize session state for DataFrame and batch number
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame(columns=["Slab Number", "Length", "Width", "Sq.ft", "Grade"])
if 'batch_no' not in st.session_state:
    st.session_state.batch_no = ""
if 'show_section2' not in st.session_state:
    st.session_state.show_section2 = False

# Streamlit app layout
st.title("Slab Measurements Entry")

# Section 1: User details
st.header("Section 1: User Details")
supplier_name = st.text_input("Supplier Name")
batch_no = st.text_input("Batch Number", st.session_state.batch_no)
color = st.text_input("Color")
marker = st.text_input("Marker")
date = st.date_input("Date", value=datetime.today())

# Button to proceed to Section 2
if st.button("Enter Measurement"):
    if supplier_name and batch_no and color and marker:
        st.session_state.show_section2 = True
        st.session_state.batch_no = batch_no
        st.success("Proceed to enter measurements.")
    else:
        st.error("Please fill all fields in Section 1 before proceeding.")

# Section 2: Slab measurements entry (only shown if "Enter Measurement" is clicked)
if st.session_state.show_section2:
    st.header("Section 2: Slab Measurements Entry")
    measurement_unit = st.selectbox("Measurement Unit", ["inches (in)", "centimeters (cm)"])
    slab_number = st.text_input("Slab Number")
    length = st.number_input("Length ", min_value=0)
    width = st.number_input("Width ", min_value=0)
    grade = st.text_input("Grade")

    # Button to add slab measurements to DataFrame
    if st.button("Next"):
        if slab_number and length and width:   # grade is not mandatory
 
            # Calculate square feet
            sq_ft = length * width

            # Create new record with dynamic column names
            new_record = pd.DataFrame([{
                "Slab Number": slab_number,
                "Length": length,
                "Width": width,
                "Sq.ft": sq_ft,
                "Grade": grade                
            }])
            # Append the new record to the DataFrame
            st.session_state.df = pd.concat([st.session_state.df, new_record], ignore_index=True)
            st.success("Record added successfully!")
            
            # Clear the input fields for the next record
            slab_number = ""
            length = 0
            width = 0
            grade = ""
        else:
            st.error("Please fill all fields before proceeding.")

    # Display the current DataFrame
    st.header("Current Records")
    st.dataframe(st.session_state.df)

    # Button to submit and generate Excel file
    if st.button("Submit"):
        if not st.session_state.df.empty and batch_no:
            # Create a BytesIO buffer for the Excel file
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                # Write Section 1 details to the first sheet
                section1_data = {
                    "Supplier Name": [supplier_name],
                    "Batch Number": [batch_no],
                    "Color": [color],
                    "Marker": [marker],
                    "Date": [date]
                }
                section1_df = pd.DataFrame(section1_data)
                section1_df.to_excel(writer, sheet_name="Supplier details", index=False)

                # Write slab measurements to the second sheet
                st.session_state.df.to_excel(writer, sheet_name="Slab Measurements", index=False)

            # Prepare the file for download
            output.seek(0)
            file_name = f"INS_UNP_{batch_no}.xlsx"
            st.download_button(
                label="Download Excel File",
                data=output,
                file_name=file_name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            # # Set submitted state to True to show the Clear button
            # st.session_state.submitted = True

        else:
            st.error("Please ensure all records are entered and Batch Number is provided.")
    
# if st.session_state.submitted:
#     if st.button("Clear", key="clear_button"):
#         # Reset all session state variables
#         st.rerun()
#         st.session_state.submitted = False
#         st.success("All fields have been cleared.")