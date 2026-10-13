import html
import folium
from survey_core import BOUNDARY,RING

def survey_map(points=(),pending=None):
    latitudes=[p[1] for p in RING];longitudes=[p[0] for p in RING]
    m=folium.Map(location=[sum(latitudes)/len(latitudes),sum(longitudes)/len(longitudes)],zoom_start=14,tiles='OpenStreetMap',control_scale=True)
    folium.GeoJson(BOUNDARY,name='Armoede survey boundary',style_function=lambda _: {'color':'#12685f','weight':3,'fillColor':'#2b9f8d','fillOpacity':0.08},tooltip='Armoede / Ga-Sekhaolelo survey area').add_to(m)
    m.fit_bounds([[min(latitudes),min(longitudes)],[max(latitudes),max(longitudes)]])
    for point in points:
        folium.Marker([point['lat'],point['lon']],tooltip=html.escape(point.get('label','Location')),
                      popup=folium.Popup(html.escape(point.get('label','Location')),max_width=280),icon=folium.Icon(color='green',icon='info-sign')).add_to(m)
    if pending:
        folium.CircleMarker([pending['lat'],pending['lng']],radius=8,color='#d97706',fill=True,fill_opacity=.8,tooltip='Selected point awaiting attachment').add_to(m)
    return m
